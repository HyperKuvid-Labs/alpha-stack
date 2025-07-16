from determine_tech_stack import gen_and_store_ts
from rgen_fs import generate_structure

prompt = "I want to build a python app that can handle files and folders using rust and python, with a focus on performance and scalability. The app should be able to process large datasets efficiently and provide a user-friendly interface."
gen_and_store_ts(prompt)
generate_structure()
