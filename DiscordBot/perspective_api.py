from googleapiclient import discovery
import json

API_KEY = ''

def analyze_message(message):
  client = discovery.build(
    "commentanalyzer",
    "v1alpha1",
    developerKey=API_KEY,
    discoveryServiceUrl="https://commentanalyzer.googleapis.com/$discovery/rest?version=v1alpha1",
    static_discovery=False,
  )

  analyze_request = {
    'comment': { 'text': message },
    'requestedAttributes': {'TOXICITY': {}, 'SEXUALLY_EXPLICIT': {}, 'THREAT': {}},
  }

  response = client.comments().analyze(body=analyze_request).execute()
  # print(json.dumps(response, indent=2))
  return response


