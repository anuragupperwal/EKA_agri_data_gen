import time
import json
import os
import logging
from google import genai
from google.genai import types

# Setup simple logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TextBatchJob:
    def __init__(self, job_name="agri-advisory-job"):
        self.api_key = os.environ['GEMINI_API_KEY_2'] 
        self.client = genai.Client(api_key=self.api_key)  
        self.job_name = job_name
        self.job_id = f"{job_name}_{int(time.time())}"
        self.output_dir = f"output/{self.job_id}"
        os.makedirs(self.output_dir, exist_ok=True)
        self.jsonl_path = f"{self.output_dir}/batch_requests.jsonl"

    # def prepare_prompt(self, data_bundle):
    #     """
    #     Takes the entire dictionary, converts it to a formatted JSON string,
    #     and wraps it in a strict instruction block.
    #     """
    #     # Convert the dictionary to a pretty-printed JSON string
    #     data_json = json.dumps(data_bundle, indent=2, ensure_ascii=False)
        
    #     prompt = f"""
    #     Role: Expert Agricultural Advisor for Indian farmers.
    #     Language: Hindi (Strictly).
        
    #     Input Data (JSON):
    #     ```json
    #     {data_json}
    #     ```
        
    #     Task:
    #     You are provided with a data bundle containing details about a specific crop scenario (Crop, Weather, Soil, Pest, Disease, Stage, etc.). 
    #     1. Analyze all the provided parameters in the JSON "Input Data" and fill if missing or "None". 
    #     2. Generate a practical, actionable advisory for the farmer based *only* on these specific conditions.
    #     3. If specific values (like temperature or rainfall) are provided, reference them in your reasoning.
        
    #     Constraints:
    #     - The output must be purely the advisory text in Hindi.
    #     - Tone: Respectful, clear, and authoritative (kisan mitra).
    #     """
    #     return prompt


    def prepare_prompt(self, data_bundle):
        """
        Takes the entire dictionary, converts it to a formatted JSON string,
        and wraps it in a strict instruction block with Feasibility Logic.
        """
        # Convert the dictionary to a pretty-printed JSON string
        data_json = json.dumps(data_bundle, indent=2, ensure_ascii=False)
        
        prompt = f"""
        Role: Expert Agricultural Advisor for Indian farmers (Kisan Mitra).
        Language: Hindi (Strictly).
        
        Input Data (JSON):
        ```json
        {data_json}
        ```
        
        Task:
        You are provided with a data bundle describing a specific agricultural scenario.
        
        Step 1: **Feasibility Analysis (Crucial)**
        Compare the 'Crop' requirements (Temperature, Rainfall, etc.) against the provided 'Weather' conditions and all other constraints.
        
        Step 2: **Generate Advisory**
        Based on Step 1, generate the advisory in Hindi:
        - **If the scenario is IMPOSSIBLE/FATAL**: 
          * Clearly state that farming this crop is NOT recommended.
          * Explain *why* clearly.
          * Do NOT give false hope or generic fertilizer tips for a dying crop.
        - **If the scenario is STRESSFUL but SALVAGEABLE**: 
          * Acknowledge the stress (e.g., "Drought stress", etc).
          * Provide specific mitigation steps.
        - **If the scenario is IDEAL**: 
          * Focus on yield maximization and standard care.

        Constraints:
        - Output strictly in **valid JSON** with a single key: "advisory_hindi".
        - Use simple, clear Hindi suitable for farmers. Use bullet points for steps.
        - Reference specific numbers from the input (e.g., "Since rainfall is 0mm...", etc).
        """
        return prompt


    def create_jsonl(self, input_file_path):
        """
        Reads input bundles from a JSONL file line-by-line and writes 
        formatted Batch API requests to the output JSONL file.
        This allows processing massive datasets without memory issues.
        """

        logger.info(f"Reading from {input_file_path}...")
        logger.info(f"Writing batch requests to {self.jsonl_path}...")
        request_count = 0
        
        with open(input_file_path, 'r', encoding='utf-8') as infile, \
                    open(self.jsonl_path, 'w', encoding='utf-8') as outfile:
            
            for index, line in enumerate(infile):
                try:
                    bundle = json.loads(line.strip())
                    # Create Custom ID
                    custom_id = bundle.get('bundle_id', f"req_{index}")
                    # Generate Prompt
                    prompt_text = self.prepare_prompt(bundle)
                    # Construct Request Object
                    request_entry = {
                        "custom_id": custom_id,
                        "method": "POST",
                        "url": "/v1beta/models/gemini-2.5-flash:generateContent", 
                        "body": {
                            "contents": [{"parts": [{"text": prompt_text}]}],
                            "generationConfig": {
                                "responseMimeType": "application/json", 
                                "temperature": 0.2,
                                "thinkingConfig": {
                                    "includeThoughts": True 
                                }
                            }
                        }
                    }
                    
                    #write to batch file
                    outfile.write(json.dumps(request_entry) + "\n")
                    request_count += 1
                    
                except json.JSONDecodeError:
                    logger.error(f"Skipping invalid JSON at line {index}")
                    continue
        
        logger.info(f"Successfully created batch file with {request_count} requests.")


    def submit_job(self):
        """Uploads the JSONL and starts the Batch Job"""
        logger.info("Uploading JSONL file to Gemini...")
        batch_input_file = self.client.files.upload(
            file=self.jsonl_path,
            config=types.UploadFileConfig(mime_type="text/plain") 
        )
        
        logger.info(f"File uploaded: {batch_input_file.name}. Starting Batch Job...")
        
        self.batch_job = self.client.batches.create( 
            model="models/gemini-2.5-flash",
            src=batch_input_file.name,
            config=types.BatchJobConfig(display_name=self.job_id)
        )
        
        logger.info(f"Batch Job Created: {self.batch_job.name}")
        return self.batch_job


    def wait_for_completion(self):
        """Polls the job status"""
        while True:
            job_status = self.client.batches.get(name=self.batch_job.name)
            state = job_status.state.name 
            logger.info(f"Job Status: {state}")
            
            if state in ["JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED"]:
                return job_status
            
            time.sleep(30) 


    def download_and_parse_results(self):
        """Downloads the result file and parses the outputs"""
        job = self.client.batches.get(name=self.batch_job.name)
        
        if job.state.name != "JOB_STATE_SUCCEEDED":
            logger.error("Job failed or incomplete.") 
            return 

        output_file_name = job.output_file.name
        logger.info(f"Downloading results from {output_file_name}...")
        
        # Download raw content
        content = self.client.files.content(file=output_file_name)
        
        # Save Raw Output
        raw_path = f"{self.output_dir}/raw_results.jsonl"
        with open(raw_path, 'wb') as f:
            f.write(content)
            
        # Parse and Separate Files
        # self._parse_raw_results(raw_path)


    # def _parse_raw_results(self, raw_path):
    #     logger.info("Parsing results...")
    #     with open(raw_path, 'r', encoding='utf-8') as f:
    #         for line in f:
    #             try:
    #                 response_item = json.loads(line)
    #                 custom_id = response_item.get("custom_id", "unknown_id")
                    
    #                 # Extract the actual model generation
    #                 # Note: structure differs slightly based on success/error
    #                 if "response" in response_item:
    #                     model_output = response_item["response"]["candidates"][0]["content"]["parts"][0]["text"]
                        
    #                     # Save individual file
    #                     output_filename = f"{self.output_dir}/{custom_id}.json"
    #                     with open(output_filename, "w", encoding="utf-8") as out_f:
    #                         out_f.write(model_output)
    #                 else:
    #                     logger.warning(f"Item {custom_id} failed: {response_item}")
                        
    #             except Exception as e:
    #                 logger.error(f"Error parsing line: {e}")


if __name__ == "__main__":

    processor = TextBatchJob()
    
    processor.create_jsonl("data/bundles/bundles.jsonl")
    
    processor.submit_job()
    
    # processor.wait_for_completion()
    
    # processor.download_and_parse_results()