import requests

API_KEY = 'aa14874600855457b5a838ec894a06ae'
API_URL = 'https://api-football-v1.p.rapidapi.com/v3/fixtures'

headers = {
    'X-RapidAPI-Key': API_KEY,
    'X-RapidAPI-Host': 'api-football-v1.p.rapidapi.com'
}

# Vous pouvez ajuster les paramètres selon ce que vous voulez récupérer
querystring = {
    'date': '2024-11-29',  # Exemple de date
    'league': '39',        # Premier League, par exemple
    'season': '2023'
}

response = requests.get(API_URL, headers=headers, params=querystring)

if response.status_code == 200:
    print("Connexion réussie!")
    print(response.json())  # Cela affichera les données brutes
else:
    print(f"Erreur : {response.status_code}")
