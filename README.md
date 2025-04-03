``` markdown
# Mistral-II Application

A Flask application that integrates AWS cost monitoring with Mistral AI's language model capabilities.

## Features

- Interactive chat interface with Mistral AI
- AWS cost summary and forecasting
- Service-specific cost breakdowns
- Interactive data visualization

## Prerequisites

- Python 3.8 or higher
- AWS account with Cost Explorer enabled
- Mistral AI API access

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/mistral-ii.git
   cd mistral-ii
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

The application uses a YAML configuration file to manage credentials and settings.

1. Create your configuration file by copying the example:
   ```bash
   cp example.config.yml config.yml
   ```

2. Edit `config.yml` and add your credentials:
   ```yaml
   mistral:
     api_key: your_mistral_api_key_here
     model: mistral-medium
     api_url: https://api.mistral.ai/v1/chat/completions

   aws:
     access_key: your_aws_access_key_here
     secret_key: your_aws_secret_key_here
     region: us-east-1
   ```

   > **IMPORTANT**: Never commit your `config.yml` file with actual credentials to version control.

## Running the Application

Start the Flask application:
```bash
python app.py
```

The application will be available at http://127.0.0.1:5000/

All log messages will be displayed in the console, making it easier to debug and monitor application activity.

## Usage

### Chat Interface
- Navigate to the main page to interact with Mistral AI
- Type your queries in the chat box
- Explore AI-generated responses

### AWS Cost Analysis
- Access cost summaries and forecasts
- View service-specific cost breakdowns
- Analyze monthly spending patterns



### Logging
The application logs information to stdout, allowing you to see all log messages directly in your console. Log levels can be adjusted in the configuration if needed.

### Important Implementation Note
The application uses direct credential initialization for AWS Cost Explorer client instead of relying on AWS session. This ensures the credentials are explicitly passed for each AWS service interaction.

### Adding New Features
To add new features:
1. Create feature branch
2. Implement and test your changes
3. Submit a pull request

## Troubleshooting

Common issues:
- **AWS credentials not working**: Ensure you have the correct permissions in your AWS account and Cost Explorer API is enabled
- **Mistral API errors**: Verify your API key and quota
- **Missing dependencies**: Run `pip install -r requirements.txt` to ensure all dependencies are installed

## License

[Specify your license here]

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
```
