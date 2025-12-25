import json
import os
import time
import logging
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class BatchValidator:
    def __init__(self):
        self.api_key = os.getenv('GOOGLE_API_KEY_SOKET')
        self.model_name = "gemini-2.5-flash" 
        self.client = genai.Client(api_key=self.api_key)
        
        # Paths
        self.job_id = f"validation_batch_{int(time.time())}"
        self.input_path = "data/bundles/bundles.jsonl"
        self.batch_request_file = f"data/bundles/classify/{self.job_id}_requests.jsonl"
        self.raw_results_file = f"data/bundles/classify/{self.job_id}_results.jsonl"
        self.valid_output = "data/bundles/classify/valid_bundles.jsonl"
        self.invalid_output = "data/bundles/classify/invalid_bundles.jsonl"

        self.system_instruction = """
        You are an Expert Agricultural Scientist. Validate these scenarios.
        Logic:
        1. Pest/Crop Mismatch (e.g. Pink Bollworm affects Cotton ONLY).
        2. Weather/Stress Mismatch (e.g. Drought cannot happen in Heavy Rain).
        3. Healthy Mismatch (No Stress cannot exist in Frost/Drought).
        Or any other mismatch.
        
        Output: JSON mapping ID to 1 (Valid) or 0 (Invalid).
        Example: { "1": 1, "2": 0 , ...}
        """

    def create_batch_file(self, chunk_size=50):
        """1. Reads bundles and creates a JSONL file for Batch API."""
        if not os.path.exists(self.input_path):
            logger.error(f"Input file not found: {self.input_path}")
            return False

        logger.info("Reading input bundles...")
        all_bundles = []
        with open(self.input_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    all_bundles.append(json.loads(line))
        
        logger.info(f"Loaded {len(all_bundles)} bundles. Creating batch requests...")

        with open(self.batch_request_file, 'w', encoding='utf-8') as f_out:
            # Split into chunks of 50
            for i in range(0, len(all_bundles), chunk_size):
                chunk = all_bundles[i : i + chunk_size]
                
                # Format the data string to save tokens
                prompt_data = []
                for b in chunk:
                    prompt_data.append({
                        "id": b["id"],
                        "text": f"Crop: {b['crop']['label']} ({b['crop']['id']}), Stage: {b['growth_stage']['label']}, Weather: {b['weather']['label']} ({b['weather']['id']}), Stress: {b['stress']['label']} ({b['stress']['id']})"
                    })

                prompt = f"""
                Classify these {len(prompt_data)} scenarios. 
                Return JSON mapping ID to 0 or 1.
                Scenarios: {json.dumps(prompt_data, ensure_ascii=False)}
                """

                # Create Batch Request Object
                request_entry = {
                    "custom_id": f"chunk_{i}", # Helps track which chunk this is
                    "request": {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "responseMimeType": "application/json"
                        },
                        "systemInstruction": {
                            "parts": [{"text": self.system_instruction}]
                        }
                    }
                }
                f_out.write(json.dumps(request_entry) + "\n")
        
        logger.info(f"Batch request file created: {self.batch_request_file}")
        return True

    def submit_and_wait(self):
        """Uploads file and starts the Batch Job."""
        logger.info("Uploading batch file to Google...")
        batch_input_file = self.client.files.upload(
            file=self.batch_request_file,
            config=types.UploadFileConfig(display_name="my-batch-requests", mime_type="text/plain") 
        )
        
        logger.info(f"Starting Batch Job with model {self.model_name}...")
        job = self.client.batches.create( 
            model=self.model_name,
            src=batch_input_file.name,
            config={
                'display_name': self.job_id,
            },
        )
        
        logger.info(f"Job {job.name} started. Waiting for completion...")
        
        # Poll for status
        while True:
            job = self.client.batches.get(name=job.name)
            if job.state.name == "JOB_STATE_SUCCEEDED":
                logger.info("Job Completed Successfully!")
                break
            elif job.state.name in ["JOB_STATE_FAILED", "JOB_STATE_CANCELLED"]:
                logger.error(f"Job Failed: {job.state.name}")
                return False
            
            logger.info(f"Status: {job.state.name}... (Waiting 30s)")
            time.sleep(60)
            
        # Download Results
        content = self.client.files.download(file=job.dest.file_name)
        with open(self.raw_results_file, 'wb') as f:
            f.write(content)
            
        logger.info(f"Results downloaded to {self.raw_results_file}")
        return True

    def parse_and_split(self):
        """parses results and splits the original file."""
        logger.info("Parsing results...")
        
        validation_map = {}
        
        # Load the raw results from Google
        with open(self.raw_results_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    resp = json.loads(line)
                    # Extract the JSON string from the model response
                    candidates = resp['response']['candidates'][0]['content']['parts'][0]['text']
                    chunk_decisions = json.loads(candidates)
                    
                    # Add to our main map (force keys to strings)
                    for k, v in chunk_decisions.items():
                        validation_map[str(k)] = v
                except Exception as e:
                    logger.error(f"Error parsing a result line: {e}")

        logger.info(f"Loaded {len(validation_map)} validation decisions.")

        # Split the original file
        valid_cnt = 0
        invalid_cnt = 0
        
        with open(self.input_path, 'r', encoding='utf-8') as infile, \
             open(self.valid_output, 'w', encoding='utf-8') as valid_out, \
             open(self.invalid_output, 'w', encoding='utf-8') as invalid_out:
            
            for line in infile:
                bundle = json.loads(line)
                b_id = str(bundle['id'])
                
                # Default to Invalid (0) if LLM missed it (safety first)
                is_valid = validation_map.get(b_id, 0)
                
                if is_valid == 1:
                    valid_out.write(line)
                    valid_cnt += 1
                else:
                    if b_id not in validation_map:
                        bundle['validation_status'] = "LLM_MISSED"
                    else:
                        bundle['validation_status'] = "LLM_REJECTED"
                    
                    invalid_out.write(json.dumps(bundle, ensure_ascii=False) + "\n")
                    invalid_cnt += 1

        print("="*40)
        print(f"BATCH PROCESS COMPLETE")
        print(f"Valid Scenarios: {valid_cnt}")
        print(f"Invalid Scenarios: {invalid_cnt}")
        print("="*40)

if __name__ == "__main__":
    validator = BatchValidator()
    validator.create_batch_file()
    validator.submit_and_wait()
    validator.parse_and_split()