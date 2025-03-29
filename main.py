import json
import os
import time
from docx import Document
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OUTPUT_LANGUAGE = os.getenv("OUTPUT_LANGUAGE") or "Russian"
OUTPUT_PART_TITLE = json.loads(os.getenv("OUTPUT_PART_TITLE_MAP")) if os.getenv("OUTPUT_PART_TITLE") else {
    "introduction": "Введение",
    "conclusion": "Заключение",
    "sourceList": "Список использованных источников"
}
MODEL = os.getenv("MODEL") or "gpt-4o-2024-11-20"
MAX_TOKENS = os.getenv("MAX_TOKENS") or 4000
TEMPERATURE = os.getenv("TEMPERATURE") or 0.7
OUT_DIR = './out'

os.makedirs(OUT_DIR, exist_ok=True)

client = OpenAI(api_key=os.getenv('OPEN_AI_API_KEY'))

class EssayOutlinePart(BaseModel):
    name: str
    subpartNames: list[str]

class EssayOutline(BaseModel):
    mainParts: list[EssayOutlinePart]


def generate_outline(topic):
    prompt = f"""Write only the outline of the essay organized in 3-5 main parts,
    each containing at least 2-4 subparts with arguments, examples, numbers, stats, quotes (depending on context)
    for the following topic and convert it into the given structure. Don't include introduction and conclusion.
    Use number prefixes for part and subpart names, for example "1. PartName", "1.1 SubpartName"
    Topic: {topic}"""
    response = client.beta.chat.completions.parse(
        model=MODEL,
        messages=[
            {"role": "system", "content": f"You are a helpful assistant that generates essay outlines in {OUTPUT_LANGUAGE}."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        response_format=EssayOutline
    )
    return response.choices[0].message.content

def save_outline_to_json(outline, filename):
    try:
        outline_json = json.loads(outline)
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(outline_json, f, ensure_ascii=False, indent=4)
        print(f"Outline saved to {filename}")
    except json.JSONDecodeError:
        print("Error: Generated outline is not valid JSON. Please check the prompt and try again.")

def generate_introduction(topic, outline):
    prompt = f"""Write the introduction (hook, presentation of the subject, problem statement, and plan announcement) for an essay according the following topic and outline.
    Topic: {topic}
    Outline: {outline}
    """
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": f"You are a helpful assistant that writes essay introductions in {OUTPUT_LANGUAGE}."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE
    )
    return response.choices[0].message.content.strip()

def generate_subpart(subpart_name, outline):
    prompt = f"""
    ONLY write text for subpart {subpart_name} for an essay using the following outline. Don't include subpart name in output.
    Outline: {outline}
    """
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": f"You are a helpful assistant that writes essay subparts in {OUTPUT_LANGUAGE}."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE
    )
    return response.choices[0].message.content.strip()

def generate_conclusion(topic, outline):
    prompt = f"""
    Write the conclusion, that resumes what is said in essay for the following topic and outline.
    Topic: {topic}
    Outline: {outline}
    """
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": f"You are a helpful assistant that writes essay conclusions in {OUTPUT_LANGUAGE}."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE
    )
    return response.choices[0].message.content.strip()

def generate_sources(topic, outline):
    prompt = f"""
    Generate a list of sources that can be used to write an essay on the following topic and outline. Each source should start from the new line and contain the order number.
    Topic: {topic}
    Outline: {outline}
    """
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": f"You are a helpful assistant that generates essay sources in {OUTPUT_LANGUAGE}."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE
    )
    return response.choices[0].message.content.strip()

def save_essay_to_docx(essay_text, filename):
    doc = Document()
    lines = essay_text.split('\n')

    for line in lines:
        doc.add_paragraph(line.strip())

    doc.save(filename)

import json

def format_json_to_hierarchy(data):
    formatted_text = ""
    
    for main_part in data["mainParts"]:
        formatted_text += f"{main_part["name"]}\n"
        
        for subpart in main_part["subpartNames"]:
            formatted_text += f"    {subpart}\n"
        
    return formatted_text

#TODO: possible improvements
# 1. Add opportunity to use web search tool to generate some of essay parts(select manually + always use web search tool to generate sources list), aslo:
#      a) Add ability to generate sources list using web search tool or insert them manually
#      b) Use these sources as context to generate the whole essay
# 2. Pass summarized version of all previous subparts for next supbart generation to give model additional context:
#      a) For the first supbart ask LLM to generate text of part and summary for this text
#      b) Past summary of the first subpart to the model context and ask to update this summary for the second subpart
#      c) For the third supbart pass summary generated for the previous two suparts, continue with this approach until essay generation is finished
# 3. Add mechanism to fight with AI detectors
def main():
    # Step 1: Get essay topic from user
    topic = input("Enter the essay topic: ")

    # Step 2: Generate outline
    print("Generating outline...")
    outline = generate_outline(topic)
    print("Generated Outline:")
    print(outline)

    # Step 3: Save outline to JSON file
    outline_filename = f"{OUT_DIR}/essay_outline.json"
    save_outline_to_json(outline, outline_filename)

    # Ask user to edit the JSON file
    input(f"Please edit the file '{outline_filename}' and press Enter to continue...")

    # Load the edited outline
    with open(outline_filename, 'r', encoding='utf-8') as f:
        outline_json = json.load(f)

    formatted_outline = format_json_to_hierarchy(outline_json)


    # Step 4: Generate introduction
    print("Generating introduction...")
    introduction = generate_introduction(topic, formatted_outline)
    print(introduction)


    essay_text = f"{formatted_outline}\n\n{OUTPUT_PART_TITLE["introduction"]}\n{introduction}\n\n"

    # Step 5: Generate subparts
    for part in outline_json["mainParts"]:
        part_name = part["name"]
        subparts = part["subpartNames"]
        essay_text += f"{part_name}\n\n"
        for subpart in subparts:
            print(f"Generating {subpart}...")
            #TODO: context for part generation containing previous parts?
            subpart_text = generate_subpart(subpart, formatted_outline)
            essay_text += f"{subpart}\n{subpart_text}\n\n"

    # Step 6: Generate conclusion
    print("Generating conclusion...")
    conclusion = generate_conclusion(topic, formatted_outline)
    print("Conclusion:")
    print(conclusion)
    essay_text += f"{OUTPUT_PART_TITLE["conclusion"]}\n{conclusion}\n\n"

    # Step 7: Generate sources
    print("Generating sources...")
    sources = generate_sources(topic, formatted_outline)
    print("Sources:")
    print(sources)
    essay_text += f"{OUTPUT_PART_TITLE["sourceList"]}\n{sources}\n\n"

    # Save the final essay to a .docx file
    essay_filename = f"{OUT_DIR}/{topic}-{time.time()}.docx"
    save_essay_to_docx(essay_text, essay_filename)
    print(f"Essay saved to {essay_filename}")

if __name__ == "__main__":
    main()