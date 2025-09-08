# app/use_generator.py
# app/use_generator.py

from pathlib import Path
import sys
import json

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from generator.orchestrator import Orchestrator

def main():
    try:
        # Read the spec text
        with open("/home/ambreen/Downloads/pandura-chat/parsed_text.txt", "r", encoding="utf-8") as f:
            spec_text = f.read()
        
        # Initialize the orchestrator
        orch = Orchestrator(out_dir="./builds")
        
        # Generate the project
        result = orch.generate(
            spec_text=spec_text,
            vendor="Siemens",  # or "Rockwell", "Beckhoff"
            project_name="ConveyorLine_Palletizer"
        )
        
        # Print the result
        print("Generation completed successfully!")
        print("Result:", json.dumps(result, indent=2))
        
        # If you want to access specific fields, check if they exist first
        if isinstance(result, dict):
            if "bundle" in result and isinstance(result["bundle"], dict):
                print("\nProject directory:", result["bundle"].get("project_dir", "Not specified"))
            else:
                print("\nNo bundle information found in the result")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

# from pathlib import Path
# import sys
# # Add project root to Python path
# project_root = str(Path(__file__).parent.parent)
# if project_root not in sys.path:
#     sys.path.insert(0, project_root)
# from generator.orchestrator import Orchestrator
# spec_text = open("/home/ambreen/Downloads/pandura-chat/parsed_text.txt","r",encoding="utf-8").read()
# orch = Orchestrator(out_dir="./builds")
# bundle = orch.generate(
# spec_text=spec_text,
# vendor="Siemens",
# # or "Rockwell", "Beckhoff"
# project_name="ConveyorLine_Palletizer"
# )
# print("Project at:", bundle["bundle"]["project_dir"])