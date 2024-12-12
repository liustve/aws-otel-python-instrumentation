import asyncio
import json

import aiohttp
import requests

import certifi
import urllib3
import urllib.request
import requests
import httpx

def call_api_urllib(region='us-east-1'):
    
    endpoint = 'https://ynz9vimr0l.execute-api.us-east-1.amazonaws.com/test'
    request = urllib.request.Request(
        url=endpoint,
        method='GET'
    )

    with urllib.request.urlopen(request) as response:
        response_data = response.read().decode('utf-8')
        return json.loads(response_data)

def call_api_urllib3(region='us-east-1'):
    
    endpoint = 'https://ynz9vimr0l.execute-api.us-east-1.amazonaws.com/test'
    
    
    # Create urllib3 pool manager with SSL verification
    urll3 = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
    
    try:
        # Make the request
        response = urll3.request(
            'GET',
            endpoint,
        )
        
        # Process response
        if response.status == 200:
            response_data = response.data.decode('utf-8')
            # lambdas = list_lambda_functions()
            return json.loads(response_data)
        else:
            print(f"HTTP Error: {response.status}")
            print(f"Response headers: {response.headers}")
            print(f"Response body: {response.data.decode('utf-8')}")
            raise Exception(f"Request failed with status {response.status}")
            
    except Exception as e:
        print(f"Error: {str(e)}")
        raise
    finally:
        urll3.clear()

def call_api_requests(region='us-east-1'):
    
    endpoint = 'https://ynz9vimr0l.execute-api.us-east-1.amazonaws.com/test'
    

    # Make the request using requests library
    response = requests.get(endpoint)
        
    # Raise an exception for bad status codes
    response.raise_for_status()

def call_api_httpx(region='us-east-1'):
    endpoint = 'https://ynz9vimr0l.execute-api.us-east-1.amazonaws.com/test'
    
    # Make the request using httpx library
    client = httpx.Client()
    response = client.get(endpoint)
    
    return response.json()

async def call_api_aiohttp(region='us-east-1'):
    endpoint = 'https://ynz9vimr0l.execute-api.us-east-1.amazonaws.com/test'
    
    async with aiohttp.ClientSession() as session:
        async with session.get(endpoint) as response:
            return await response.json()

# lambda function
def lambda_handler(event, context):
    response = None
    if event == '1':
        response = call_api_urllib()
    if event == '2':
        response = call_api_urllib3()
    if event == '3':
        response = call_api_requests()
    if event == '4':
        response = call_api_httpx()
    if event == '5':
        response = asyncio.run(call_api_aiohttp())

    return {"statusCode": 200, "body": response}