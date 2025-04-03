from flask import Flask, request, jsonify, render_template
from flask_cors import CORS  # Add CORS support
import requests
import json
import os
import boto3
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
import logging
import yaml
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# API Configuration
config_path = os.path.join(os.path.dirname(__file__), 'config.yml')
with open(config_path, 'r') as config_file:
    config = yaml.safe_load(config_file)

# Mistral configuration
API_KEY = config['mistral']['api_key']
MODEL = config['mistral']['model']
MISTRAL_API_URL = config['mistral']['api_url']

# AWS configuration
AWS_ACCESS_KEY = config['aws']['access_key']
AWS_SECRET_KEY = config['aws']['secret_key']
AWS_REGION = config['aws']['region']

# Create a session
aws_session = boto3.Session(
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION
)

# Create the Cost Explorer client
try:
    ce_client = aws_session.client('ce')
    logger.info("AWS Cost Explorer client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize AWS Cost Explorer client: {str(e)}")
    ce_client = None


@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error serving index.html: {str(e)}")
        return jsonify({"error": str(e)}), 500

def get_aws_cost_summary(start_date=None, end_date=None, granularity="MONTHLY"):
    """
    Get a summary of AWS costs for the specified time period
    """
    try:
        # Check if AWS client is properly initialized
        ce_client = boto3.client(
            'ce',
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION
        )


        # If dates not provided, default to last 30 days
        if not start_date:
            end = datetime.now()
            start = end - timedelta(days=30)
            start_date = start.strftime('%Y-%m-%d')
            end_date = end.strftime('%Y-%m-%d')
        # If only start date provided, default end date to today
        elif not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')

        logger.info(f"Getting cost summary from {start_date} to {end_date} with {granularity} granularity")

        # Call AWS Cost Explorer API
        response = ce_client.get_cost_and_usage(
            TimePeriod={
                'Start': start_date,
                'End': end_date
            },
            Granularity=granularity,
            Metrics=['UnblendedCost', 'UsageQuantity'],
            GroupBy=[
                {
                    'Type': 'DIMENSION',
                    'Key': 'SERVICE'
                }
            ]
        )

        # Process and format the response
        results = {
            'total_cost': 0.0,
            'start_date': start_date,
            'end_date': end_date,
            'granularity': granularity,
            'services': []
        }

        if 'ResultsByTime' in response:
            for time_period in response['ResultsByTime']:
                period_start = time_period['TimePeriod']['Start']
                period_end = time_period['TimePeriod']['End']

                for group in time_period['Groups']:
                    service_name = group['Keys'][0]
                    cost = float(group['Metrics']['UnblendedCost']['Amount'])
                    results['total_cost'] += cost

                    results['services'].append({
                        'service_name': service_name,
                        'cost': round(cost, 2),
                        'currency': group['Metrics']['UnblendedCost']['Unit']
                    })

            # Sort services by cost (descending)
            results['services'].sort(key=lambda x: x['cost'], reverse=True)
            results['total_cost'] = round(results['total_cost'], 2)
            print("=== RAW AWS COST SUMMARY DATA ===")
            print(response)
            print("=================================")

        return results

    except Exception as e:
        logger.error(f"Error getting AWS cost summary: {str(e)}", exc_info=True)
        return {
            "error": f"Failed to retrieve AWS cost data: {str(e)}",
            "help": "Please ensure your AWS credentials are properly configured with Cost Explorer access permissions."
        }


def get_aws_cost_forecast(days=30, granularity="MONTHLY"):
    """
    Get a forecast of AWS costs for future periods
    """
    try:
        # Check if AWS client is properly initialized
        if not ce_client:
            logger.error("AWS Cost Explorer client not initialized")
            return {
                "error": "AWS credentials not configured properly. Please set up your AWS credentials."
            }

        # Calculate start and end dates
        start = datetime.now()
        end = start + timedelta(days=days)
        start_date = start.strftime('%Y-%m-%d')
        end_date = end.strftime('%Y-%m-%d')

        logger.info(f"Getting cost forecast from {start_date} to {end_date} with {granularity} granularity")

        # Call AWS Cost Explorer API for forecast
        response = ce_client.get_cost_forecast(
            TimePeriod={
                'Start': start_date,
                'End': end_date
            },
            Metric='UNBLENDED_COST',
            Granularity=granularity
        )

        # Process and format the response
        results = {
            'forecast_total': float(response.get('Total', {}).get('Amount', 0)),
            'currency': response.get('Total', {}).get('Unit', 'USD'),
            'start_date': start_date,
            'end_date': end_date,
            'granularity': granularity,
            'forecast_by_time': []
        }

        if 'ForecastResultsByTime' in response:
            for period in response['ForecastResultsByTime']:
                results['forecast_by_time'].append({
                    'start': period['TimePeriod']['Start'],
                    'end': period['TimePeriod']['End'],
                    'amount': round(float(period['MeanValue']), 2),
                    'currency': period['Unit']
                })

        return results

    except Exception as e:
        logger.error(f"Error getting AWS cost forecast: {str(e)}", exc_info=True)
        return {
            "error": f"Failed to retrieve AWS cost forecast: {str(e)}",
            "help": "Please ensure your AWS credentials are properly configured with Cost Explorer access permissions."
        }


def get_aws_service_costs(service_name, start_date=None, end_date=None, granularity="DAILY"):
    """
    Get detailed costs for a specific AWS service
    """
    try:
        # Check if AWS client is properly initialized
        if not ce_client:
            logger.error("AWS Cost Explorer client not initialized")
            return {
                "error": "AWS credentials not configured properly. Please set up your AWS credentials."
            }

        # If dates not provided, default to last 30 days
        if not start_date:
            end = datetime.now()
            start = end - timedelta(days=30)
            start_date = start.strftime('%Y-%m-%d')
            end_date = end.strftime('%Y-%m-%d')
        # If only start date provided, default end date to today
        elif not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')

        logger.info(f"Getting costs for service {service_name} from {start_date} to {end_date}")

        # Call AWS Cost Explorer API
        response = ce_client.get_cost_and_usage(
            TimePeriod={
                'Start': start_date,
                'End': end_date
            },
            Granularity=granularity,
            Metrics=['UnblendedCost', 'UsageQuantity'],
            Filter={
                'Dimensions': {
                    'Key': 'SERVICE',
                    'Values': [service_name]
                }
            },
            GroupBy=[
                {
                    'Type': 'DIMENSION',
                    'Key': 'USAGE_TYPE'
                }
            ]
        )

        # Process and format the response
        results = {
            'service_name': service_name,
            'total_cost': 0.0,
            'start_date': start_date,
            'end_date': end_date,
            'granularity': granularity,
            'usage_details': [],
            'time_series': []
        }

        usage_types = {}

        if 'ResultsByTime' in response:
            for time_period in response['ResultsByTime']:
                period_start = time_period['TimePeriod']['Start']
                period_end = time_period['TimePeriod']['End']
                period_data = {
                    'start': period_start,
                    'end': period_end,
                    'cost': 0.0,
                    'usage_types': []
                }

                if 'Groups' in time_period:
                    for group in time_period['Groups']:
                        usage_type = group['Keys'][0]
                        cost = float(group['Metrics']['UnblendedCost']['Amount'])

                        period_data['cost'] += cost
                        period_data['usage_types'].append({
                            'usage_type': usage_type,
                            'cost': round(cost, 2)
                        })

                        # Aggregate by usage type across all time periods
                        if usage_type not in usage_types:
                            usage_types[usage_type] = 0
                        usage_types[usage_type] += cost

                results['total_cost'] += period_data['cost']
                period_data['cost'] = round(period_data['cost'], 2)
                results['time_series'].append(period_data)

        # Create aggregated usage details
        for usage_type, cost in usage_types.items():
            results['usage_details'].append({
                'usage_type': usage_type,
                'cost': round(cost, 2)
            })

        # Sort usage details by cost
        results['usage_details'].sort(key=lambda x: x['cost'], reverse=True)
        results['total_cost'] = round(results['total_cost'], 2)
        print("=== RAW AWS SERVICE COSTS DATA ===")
        print(response)
        print("==================================")

        return results

    except Exception as e:
        logger.error(f"Error getting AWS service costs: {str(e)}", exc_info=True)
        return {
            "error": f"Failed to retrieve costs for {service_name}: {str(e)}",
            "help": "Please ensure your AWS credentials are properly configured with Cost Explorer access permissions."
        }

@app.route('/api/test-aws', methods=['GET'])
def test_aws():
    """
    Test endpoint to verify AWS credentials and permissions
    """
    try:
        logger.info("Testing AWS credentials...")
        
        # Test basic AWS access
        sts = aws_session.client('sts')
        identity = sts.get_caller_identity()
        logger.info(f"AWS Identity: {identity}")
        
        # Test Cost Explorer access
        end = datetime.now()
        start = end - timedelta(days=1)
        start_date = start.strftime('%Y-%m-%d')
        end_date = end.strftime('%Y-%m-%d')
        
        logger.info(f"Testing Cost Explorer access for period {start_date} to {end_date}")
        response = ce_client.get_cost_and_usage(
            TimePeriod={
                'Start': start_date,
                'End': end_date
            },
            Granularity='DAILY',
            Metrics=['UnblendedCost']
        )
        
        return jsonify({
            "status": "success",
            "message": "AWS credentials and permissions are working correctly",
            "identity": identity,
            "cost_explorer": "Access confirmed"
        })
        
    except Exception as e:
        logger.error(f"AWS test failed: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"AWS test failed: {str(e)}",
            "help": "Please check your AWS credentials and ensure you have the required permissions."
        }), 400


@app.route('/api/chat', methods=['POST', 'GET'])
def chat():
    """
    Handles chat interactions with the Mistral API,
    including function calling for AWS cost management functions.
    """
    try:
        # Handle different request methods
        if request.method == 'GET':
            # For GET requests, simply inform that a POST is required
            logger.info("Received GET request to /api/chat, redirecting to POST")
            return jsonify({
                "message": {
                    "role": "assistant",
                    "content": "Please use a POST request with proper JSON payload containing messages."
                }
            })

        # Parse request data for POST requests
        data = request.json
        if not data:
            return jsonify({"error": "Empty or invalid JSON data"}), 400

        # Extract user messages from request
        raw_messages = data.get('messages', [])
        if not raw_messages:
            return jsonify({"error": "No messages provided"}), 400

        logger.info(f"Received chat request with {len(raw_messages)} messages")

        # Define the tools (functions) available to the model
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_aws_cost_summary",
                    "description": "Retrieves a summary of AWS costs for a specified time period",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_date": {
                                "type": "string",
                                "description": "Start date in YYYY-MM-DD format"
                            },
                            "end_date": {
                                "type": "string",
                                "description": "End date in YYYY-MM-DD format"
                            },
                            "granularity": {
                                "type": "string",
                                "enum": ["DAILY", "MONTHLY"],
                                "description": "Time granularity for the report"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_aws_cost_forecast",
                    "description": "Get a forecast of AWS costs for future periods",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "days": {
                                "type": "integer",
                                "description": "Number of days to forecast"
                            },
                            "granularity": {
                                "type": "string",
                                "enum": ["DAILY", "MONTHLY"],
                                "description": "Time granularity for the forecast"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_aws_service_costs",
                    "description": "Get detailed costs for a specific AWS service",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "service_name": {
                                "type": "string",
                                "description": "AWS service name (e.g., Amazon EC2, Amazon S3)"
                            },
                            "start_date": {
                                "type": "string",
                                "description": "Start date in YYYY-MM-DD format"
                            },
                            "end_date": {
                                "type": "string",
                                "description": "End date in YYYY-MM-DD format"
                            },
                            "granularity": {
                                "type": "string",
                                "enum": ["DAILY", "MONTHLY"],
                                "description": "Time granularity for the report"
                            }
                        },
                        "required": ["service_name"]
                    }
                }
            }
        ]

        # Set up request to Mistral API
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }

        payload = {
            "model": MODEL,
            "messages": raw_messages,
            "tools": tools,
            "tool_choice": "auto"  # Let the model decide when to use tools
        }

        logger.info(f"Sending request to Mistral API with {len(tools)} tools defined")

        # Debug log the payload (optional, remove in production)
        logger.debug(f"Request payload: {json.dumps(payload)}")

        # Make the API request with error handling
        try:
            response = requests.post(
                MISTRAL_API_URL,
                headers=headers,
                json=payload,
                timeout=30  # Add timeout to avoid hanging requests
            )

            logger.info(f"Received response with status code: {response.status_code}")

            # Debug log the raw response (optional, remove in production)
            logger.debug(f"Raw response: {response.text}")

            # Handle HTTP errors
            if response.status_code != 200:
                logger.error(f"API error: {response.status_code} - {response.text}")
                return jsonify({
                    "error": f"Mistral API error ({response.status_code}): {response.text}"
                }), 500

            # Parse the response
            response_data = response.json()

            # Check if the response has the expected structure
            if "choices" not in response_data or not response_data["choices"]:
                logger.error(f"Unexpected API response structure: {json.dumps(response_data)}")
                return jsonify({
                    "message": {
                        "role": "assistant",
                        "content": "I'm sorry, but I received an invalid response from the API. Please try again."
                    }
                }), 200  # Return 200 for frontend compatibility

            assistant_message = response_data["choices"][0]["message"]

            # Check if tool_calls exists and is not None before checking its length
            if assistant_message.get("tool_calls"):
                logger.info(f"Model requested to use tools: {len(assistant_message['tool_calls'])} call(s)")

                # Process each tool call
                messages = raw_messages.copy()
                messages.append(assistant_message)

                tool_calls = assistant_message["tool_calls"]
                for tool_call in tool_calls:
                    function_name = tool_call["function"]["name"]

                    # Parse function arguments
                    try:
                        function_args = json.loads(tool_call["function"]["arguments"])
                    except json.JSONDecodeError:
                        logger.error(f"Invalid function arguments: {tool_call['function']['arguments']}")
                        function_args = {}

                    logger.info(f"Executing function: {function_name} with args: {function_args}")

                    # Execute the appropriate function
                    result = None
                    if function_name == "get_aws_cost_summary":
                        result = get_aws_cost_summary(**function_args)
                    elif function_name == "get_aws_cost_forecast":
                        result = get_aws_cost_forecast(**function_args)
                    elif function_name == "get_aws_service_costs":
                        result = get_aws_service_costs(**function_args)
                    else:
                        logger.warning(f"Unknown function requested: {function_name}")
                        result = {"error": f"Unknown function: {function_name}"}

                    # Add function result as a tool message
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": function_name,
                        "content": json.dumps(result)
                    })

                # Send a follow-up request with the function results
                logger.info("Sending follow-up request with function results")
                follow_up_payload = {
                    "model": MODEL,
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": "auto"
                }

                response = requests.post(
                    MISTRAL_API_URL,
                    headers=headers,
                    json=follow_up_payload,
                    timeout=30
                )

                if response.status_code != 200:
                    logger.error(f"Follow-up API error: {response.status_code} - {response.text}")
                    return jsonify({
                        "message": {
                            "role": "assistant",
                            "content": f"I encountered an error while processing your request: {response.text}"
                        }
                    }), 200  # Return 200 for frontend compatibility

                # Parse the follow-up response
                response_data = response.json()

                # Re-check response structure for the second call
                if "choices" not in response_data or not response_data["choices"]:
                    logger.error(f"Unexpected follow-up response structure: {json.dumps(response_data)}")
                    return jsonify({
                        "message": {
                            "role": "assistant",
                            "content": "I'm sorry, but I received an invalid follow-up response. Please try again."
                        }
                    }), 200  # Return 200 for frontend compatibility

                assistant_message = response_data["choices"][0]["message"]

            # Return the final assistant message
            return jsonify({
                "message": assistant_message
            })

        except requests.exceptions.Timeout:
            logger.error("API request timed out")
            return jsonify({
                "message": {
                    "role": "assistant",
                    "content": "I'm sorry, but the request to the AI service timed out. Please try again later."
                }
            }), 200  # Return 200 for frontend compatibility

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            return jsonify({
                "message": {
                    "role": "assistant",
                    "content": "I'm sorry, but there was an error connecting to the AI service. Please try again later."
                }
            }), 200  # Return 200 for frontend compatibility

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse API response as JSON: {str(e)}")
            return jsonify({
                "message": {
                    "role": "assistant",
                    "content": "I received an invalid response from the AI service. Please try again later."
                }
            }), 200  # Return 200 for frontend compatibility

    except Exception as e:
        logger.error(f"Unexpected error in chat route: {str(e)}", exc_info=True)
        return jsonify({
            "message": {
                "role": "assistant",
                "content": f"I'm sorry, but an unexpected error occurred: {str(e)}"
            }
        }), 200  # Return 200 for frontend compatibility


if __name__ == '__main__':
    app.run(debug=True)
