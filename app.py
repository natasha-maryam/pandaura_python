import streamlit as st
import requests
import json
import os

st.set_page_config(page_title="Pandaura Code Generator", layout="wide")

st.title("🤖 Pandaura Code Generator")
st.write("Enter the PLC Functional Design Specification and the system will auto-detect the vendor (Siemens, Rockwell, Beckhoff) or generate generic code if unspecified.")

# Input box for specification text
spec_text = st.text_area(
    "Specification",
    height=250,
    value="Control spec: conveyors, alarms, modes, palletizer handshake",
)

if st.button("🚀 Generate Code"):
    if not spec_text.strip():
        st.error("Please enter a specification before generating code.")
    else:
        try:
            response = requests.post(
                "http://127.0.0.1:8000/generate_code",
                headers={"Content-Type": "application/json"},
                data=json.dumps({"spec_text": spec_text}),
            )
            result = response.json()

            if result.get("status") == "success" and result.get("files"):
                st.success("✅ Code generated successfully!")
                for file in result["files"]:
                    st.write(f"### 📂 {file}")
                    try:
                        if file.endswith((".scl", ".st", ".txt")):
                            with open(file, "r", encoding="utf-8") as f:
                                code_content = f.read()
                            # Show with syntax highlighting
                            if file.endswith(".scl"):
                                st.code(code_content, language="scl")
                            elif file.endswith(".st"):
                                st.code(code_content, language="st")
                            else:
                                st.code(code_content, language="plaintext")

                            # Add download button
                            st.download_button(
                                label=f"⬇️ Download {os.path.basename(file)}",
                                data=code_content,
                                file_name=os.path.basename(file),
                                mime="text/plain",
                            )

                        elif file.endswith(".json"):
                            with open(file, "r", encoding="utf-8") as f:
                                json_content = json.load(f)
                            st.json(json_content)

                            st.download_button(
                                label=f"⬇️ Download {os.path.basename(file)}",
                                data=json.dumps(json_content, indent=2),
                                file_name=os.path.basename(file),
                                mime="application/json",
                            )
                    except Exception as e:
                        st.warning(f"Could not display {file}: {e}")
            else:
                st.error("⚠️ No files were generated. Try adjusting the spec.")

        except Exception as e:
            st.error(f"❌ Failed to generate code: {str(e)}")








# import streamlit as st
# import requests
# import os

# API_URL = "http://127.0.0.1:8000/generate_code"

# st.set_page_config(page_title="Pandaura AS - Code Generator", layout="wide")

# st.title("🤖 Pandaura AS - PLC Code Generator")

# # User input
# spec_text = st.text_area("📋 Enter your control specification:", height=200)
# vendor = st.selectbox("🏭 Select Vendor", ["siemens", "rockwell", "beckhoff"])
# project_name = st.text_input("📂 Project Name", value="PandauraProject")

# if st.button("🚀 Generate Code"):
#     if not spec_text.strip():
#         st.error("Please enter a specification before generating.")
#     else:
#         with st.spinner("Generating code..."):
#             payload = {
#                 "spec_text": spec_text,
#                 "vendor": vendor,
#                 "project_name": project_name
#             }
#             try:
#                 response = requests.post(API_URL, json=payload)
#                 if response.status_code == 200:
#                     result = response.json()
#                     files = result.get("files", [])
#                     if not files:
#                         st.warning("⚠️ No files were generated. Try refining your spec or vendor.")
#                     else:
#                         st.success(f"✅ Code generated successfully! {len(files)} file(s) created.")
#                         for fpath in files:
#                             st.subheader(f"📄 {os.path.basename(fpath)}")
#                             try:
#                                 with open(fpath, "r", encoding="utf-8") as f:
#                                     code = f.read()
#                                 st.code(code, language="plaintext")
#                             except Exception as e:
#                                 st.error(f"Could not load file: {fpath}. Error: {e}")
#                 else:
#                     st.error(f"❌ Error {response.status_code}: {response.text}")
#             except Exception as e:
#                 st.error(f"Failed to connect to backend: {e}")








# import streamlit as st
# import requests
# import json

# st.title("Siemens S7-1500 Code Generator")
# st.write("Enter the PLC specification to generate SCL code.")

# # Input text area for the spec
# spec_text = st.text_area("Specification", height=200, value="Use the uploaded PLC Functional Design Specification as the single source of truth. Convert any Schneider/Modicon M580 Hot-Standby and X80 I/O concepts into an equivalent Siemens S7-1500 design in Structured Control Language (SCL) for TIA Portal. Implement the full control behavior described in the spec: operating modes (Auto, Semi, Manual, Maintenance, E-Stop), conveyor accumulation & jam detection, barcode-based merge/divert, palletizer handshake (Ready → InPosition → CycleStart → Complete with timeouts/faults), alarms (critical/non-critical with ack/reset), communications/diagnostics exposed for SCADA, and general performance intent. Use a clean Siemens project structure: OB1 (cyclic), OB100 (startup), FBs with instance DBs per subsystem (Conveyors, Merge/Divert, PalletizerHS, Modes, Alarms, Diag, Comms), plus UDTs for devices, alarms, and state. Keep naming consistent and comment every public tag and FB header. If redundancy is referenced, mirror the behavior and status handling within S7-1500 (assume software/state modeling if hardware redundancy isn’t configured).")

# # Button to trigger generation
# if st.button("Generate Code"):
#     try:
#         response = requests.post(
#             "http://127.0.0.1:8000/generate_code",
#             headers={"Content-Type": "application/json"},
#             data=json.dumps({"spec_text": spec_text})
#         )
#         result = response.json()
#         if result.get("status") == "success":
#             st.success("Code generated successfully!")
#             st.write("Generated files:", ", ".join(result["files"]))
#             # Display sample file content (mock for now)
#             with open(f"output/{result['files'][0]}", "r") as f:
#                 st.code(f.read(), language="scl")
#         else:
#             st.error("Error: " + str(result.get("detail", "Unknown error")))
#     except Exception as e:
#         st.error(f"Failed to generate code: {str(e)}")

# st.write("Note: This is a prototype. Full logic generation is in progress.")