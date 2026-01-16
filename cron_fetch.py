import json
import os
from Bio import Entrez
from google import genai
from datetime import datetime
import time

# Use environment variables for secrets (set by GitHub Actions)
ENTREZ_EMAIL = os.getenv("ENTREZ_EMAIL")
ENTREZ_API_KEY = os.getenv("ENTREZ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

Entrez.email = ENTREZ_EMAIL
Entrez.api_key = ENTREZ_API_KEY
client = genai.Client(api_key=GEMINI_API_KEY)

def run_automated_fetch():
    # 1. Load Config
    with open("config.json", "r") as f:
        config = json.load(f)
    
    print(f"Starting automated fetch for: {config['search_query']}")
    
    # 2. Search PubMed
    handle = Entrez.esearch(
        db="pubmed",
        term=config['search_query'],
        reldate=config['days_back'],
        datetype="pdat",
        retmax=config['max_results']
    )
    record = Entrez.read(handle)
    handle.close()
    id_list = record["IdList"]
    
    if not id_list:
        print("No new papers found.")
        return

    # 3. Fetch Details
    ids = ",".join(id_list)
    handle = Entrez.efetch(db="pubmed", id=ids, retmode="xml")
    records = Entrez.read(handle)
    handle.close()
    
    papers = []
    for article in records['PubmedArticle']:
        try:
            article_data = article['MedlineCitation']['Article']
            title = article_data.get('ArticleTitle', 'No Title')
            journal = article_data.get('Journal', {}).get('Title', 'Unknown Journal')
            abstract_raw = article_data.get('Abstract', {}).get('AbstractText', [])
            abstract = " ".join(abstract_raw) if isinstance(abstract_raw, list) else str(abstract_raw)
            article_ids = article['PubmedData']['ArticleIdList']
            doi = next((f"https://doi.org/{item}" for item in article_ids if item.attributes.get('IdType') == 'doi'), "")
            
            # 4. Analyze with Gemini
            prompt = f"Summarize this abstract in 3 bullet points highlighting the specific mechanism. Bold human trials.\n\nAbstract:\n{abstract}"
            response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            analysis = response.text
            
            papers.append({
                'title': title,
                'journal': journal,
                'abstract': abstract,
                'link': doi,
                'analysis': analysis,
                'fetched_at': datetime.now().strftime('%Y-%m-%d %H:%M')
            })
            print(f"Analyzed: {title[:50]}...")
            time.sleep(2) # Avoid hitting rate limits
        except Exception as e:
            print(f"Error processing paper: {e}")
            continue

    # 5. Save Results
    with open("results.json", "w") as f:
        json.dump(papers, f, indent=4)
    print(f"Successfully saved {len(papers)} papers to results.json")

if __name__ == "__main__":
    run_automated_fetch()
