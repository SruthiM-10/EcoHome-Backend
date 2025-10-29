from langchain_core.messages import SystemMessage
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from typing import List, Optional
import os
import re

# os.environ["OPENAI_API_KEY"] = "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"

def data_cleaning(text: str):
    """Removes a list of specific phrases from the text."""

    boilerplate_phrases = [
        "#1 Home Improvement Retailer",
        "Home Depot Credit Cards",
        "Shop All",
        "Services",
        "DIY",
        "Log In",
        "Cart",
        "Need Help? Visit our",  # Partial match is okay
        "Customer Service Center",
        "© 2000-2025 Home Depot. All Rights Reserved.",
        "Privacy & Security Statement",
        "Terms",
        # Add common PDF boilerplate too
        "Table of Contents",
        "Washer Safety",
        "Owner's Manual",
        "Installation Instructions",
        "Limited Warranty",
        "WARNING:",
        "DANGER:",
        # Add any other repeating junk you see
    ]

    # Clean based on the list
    cleaned_text = text
    for phrase in boilerplate_phrases:
        # Using replace might be slow for huge text, but it's simple
        cleaned_text = cleaned_text.replace(phrase, "")
    text_step1 = re.sub(r'\n\s*\n+', '<<PARAGRAPH_BREAK>>', cleaned_text)
    text_step2 = text_step1.replace('\n', ' ')
    final_text = text_step2.replace('<<PARAGRAPH_BREAK>>', '\n')
    final_text = re.sub(r' +', ' ', final_text).strip()
    return final_text

def setup_llm() -> Optional[ChatOpenAI]:
    if not os.environ["OPENAI_API_KEY"]:
        print("ERROR: OPENAI_API_KEY is not set. Please set your OpenAI API key.")
        return None

    try:
        return ChatOpenAI(model="gpt-4o-mini", temperature=0)
    except Exception as e:
        print(f"Error setting up LLM: {e}")
        return None

class FeaturesItem(BaseModel):
    energy: str
    durability: str
    quality: str
    repairability: str
    recyclability: str
    otherResourceUse: str
    compatibility: str
    policyAlignment: str

def extract_features(text: str, split_into_chunks: bool = False):
    #mg's account

    MAX_CHARS = 60000
    MIN_CHARS = 256

    if len(text) < MIN_CHARS:
        print(f"Input snippet text too short ({len(text)} chars), skipping LLM.")
        return []

    prompt = """
You are a marketing assistant reading a collection of relevant text snippets
scraped from a product page.
Your task is to extract and describe the following features based *only* on these snippets.

Features:
    1. energy: Energy performance/efficiency of product (kWh per use or year)
        - include specific number for efficiency in kWh per use or year
    2. durability: Durability / lifetime of product
       - include number of years or cycles product will last
    3. quality: reliability or quality of product
       - include failure rates
    4. repairability: serviceability, how easy is it to repair the product, what is the spare-parts availability, ease of disassembly
       - include repairability index
    5. recyclability: resource use and material circularity, how feasible is it to recycle this material
       - include % recycled content, recyclability
    6. otherResourceUse: operating resource use besides energy (like water usage)
       - include water per cycle, consumables
    7. compatibility: compatibility with local infrastructure (voltage, off-grid/solar compatibility, part supply chains)
    8. policyAlignment: regulatory and policy alignment (energy labels, ecodesign, repairability laws)
        - For example, if there is a law stating that heat pumps are going to be favored, mention that this product may be less or more favorable accordingly.

For each feature, keeps your descriptions detailed and concise (max 50 words).

If you cannot find a feature in the snippets below, return "N/A".

Return as ONLY a JSON array.

Relevant Snippets:
{}
"""
    results = []
    llm = setup_llm()
    structured_llm = llm.with_structured_output(FeaturesItem)
    if len(text) > MAX_CHARS or split_into_chunks:
        chunk_size = MAX_CHARS
        text_chunks = [text[i - chunk_size // 50:i + chunk_size] for i in range(chunk_size // 50, len(text), chunk_size)]
        print(f"Trying with {len(text_chunks)} chunks...")
        for chunk in text_chunks:
            try:
                system_message_prompt = [SystemMessage(content=prompt.format(chunk))]
                invoke_results = structured_llm.invoke(system_message_prompt)
                results.append(invoke_results)
            except Exception as chunk_error:
                print(f"Error processing chunk: {chunk_error}")
    else:
        try:
            system_message_prompt = [SystemMessage(content=prompt.format(text))]
            invoke_results = structured_llm.invoke(system_message_prompt)
            results.append(invoke_results)
        except Exception as error:
            print(f"Error extracting features: {error}")
            extract_features(text, split_into_chunks=True)

    return results

class ScoreItem(BaseModel):
    rank: int
    originalIndex: int

class ScoresLLM(BaseModel):
    scores: list[ScoreItem]

def compare_features(metric: str, text: str, split_into_chunks: bool = False):
    # mg's account

    MAX_CHARS = 60000
    MIN_CHARS = 256

    if len(text) < MIN_CHARS:
        print(f"Input snippet text too short ({len(text)} chars), skipping LLM.")
        return []

    prompt = """
You are a marketing assistant comparing certain appliances based on their {metric}.

You are given information about each appliance. They are labeled as "Appliance 1", "Appliance 2", etc.
Compare the information for each appliance and rank the appliances in ascending order (from 1 to N with N being the number of appliances).
    - The appliances that have the best {metric} would have the largest rank.
    For example, if the metric is price, energy, or otherResourcesUse, you should rank it higher if the value is low and vice versa.
    If the metric is durability, quality, policyAlignment, etc., you should rank it lower if the value is low and vice versa.
    
Then for each appliance return the following:
    1. their rank (from 1 to N) based on only the information given. No two appliances should have same rank.
    2. their original index: their number on the appliance's original label

Return as ONLY a JSON array.

Information about appliances:
{information}
    """
    results = []
    llm = setup_llm()
    structured_llm = llm.with_structured_output(ScoresLLM)
    if len(text) > MAX_CHARS or split_into_chunks:
        chunk_size = MAX_CHARS
        text_chunks = [text[i - chunk_size // 50:i + chunk_size] for i in
                       range(chunk_size // 50, len(text), chunk_size)]
        print(f"Trying with {len(text_chunks)} chunks...")
        for chunk in text_chunks:
            try:
                system_message_prompt = [SystemMessage(content=prompt.format(metric= metric, information=chunk))]
                invoke_results = structured_llm.invoke(system_message_prompt)
                results.append(invoke_results.scores)
            except Exception as chunk_error:
                print(f"Error processing chunk: {chunk_error}")
    else:
        try:
            system_message_prompt = [SystemMessage(content=prompt.format(metric=metric, information=text))]
            invoke_results = structured_llm.invoke(system_message_prompt)
            results.append(invoke_results.scores)
        except Exception as error:
            print(f"Error extracting features: {error}")
            extract_features(text, split_into_chunks=True)

    return results

class SnippetLLM(BaseModel):
    snippet: str

def clean_features(metric: str, text: str):
    # mg's account

    prompt = """
You are a marketing assistant reading and cleaning product descriptions.
Your task is to extract the most relevant snippets from a description of the {metric} of an appliance. 

Extract a snippet related to {description}. The total length of this snippet should be at most 10 words/numbers.
    - Prioritize getting most of the relevant numbers and their units.
Return this snippet.

Return as ONLY a JSON array.

{metric} description:
{information}
    """

    results = []
    llm = setup_llm()
    structured_llm = llm.with_structured_output(SnippetLLM)
    try:
        if metric == "energy":
            description = "Energy performance/efficiency of product and include specific number for efficiency in kWh per use or year"
        elif metric == "durability":
            description = "Durability/lifetime of product and include number of years or cycles product will last"
        elif metric == "quality":
            description = "Reliability/quality of product and include failure rates"
        elif metric == "repairability":
            description = "serviceability, how easy is it to repair the product, what is the spare-parts availability, ease of disassembly and include repairability index"
        elif metric == "recyclability":
            description = "resource use and material circularity, how feasible is it to recycle this material and include % recycled content, recyclability"
        elif metric == "otherResourceUse":
            description = "operating resource use besides energy (like water usage, water per cycles)"
        elif metric == "compatibility":
            description = "compatibility with local infrastructure (voltage, off-grid/solar compatibility, part supply chains)"
        else:
            description = "regulatory and policy alignment (energy labels, ecodesign, repairability laws)"
        system_message_prompt = [SystemMessage(content=prompt.format(metric=metric, description= description, information=text))]
        invoke_results = structured_llm.invoke(system_message_prompt)
        results.append(invoke_results.model_dump())
    except Exception as error:
        print(f"Error extracting features: {error}")
    return results