from googleapiclient import discovery
import json
import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()
API_KEY = os.getenv("API_KEY")


def analyze_message(message):
    client = discovery.build(
        "commentanalyzer",
        "v1alpha1",
        developerKey=API_KEY,
        discoveryServiceUrl="https://commentanalyzer.googleapis.com/$discovery/rest?version=v1alpha1",
        static_discovery=False,
    )

    analyze_request = {
        "comment": {"text": message},
        "requestedAttributes": {"TOXICITY": {}, "SEXUALLY_EXPLICIT": {}, "THREAT": {}},
        "languages": ["en"],
    }

    response = client.comments().analyze(body=analyze_request).execute()
    # print(json.dumps(response, indent=2))
    return response


def eval_text(message):
    """'
    Use Google Perspective API to scan for toxicity and sexually explicit content.
    """
    message_score = analyze_message(message)
    return message_score


def score_format(scores):
    """
    Formats the scores json returned by Google Perspective API.
    """
    results = {}
    results["scores"] = {}
    results["scores"]["toxicity"] = scores["attributeScores"]["TOXICITY"][
        "summaryScore"
    ]["value"]
    results["scores"]["sexually_explicit"] = scores["attributeScores"][
        "SEXUALLY_EXPLICIT"
    ]["summaryScore"]["value"]
    results["scores"]["threat"] = scores["attributeScores"]["THREAT"]["summaryScore"][
        "value"
    ]

    return results
