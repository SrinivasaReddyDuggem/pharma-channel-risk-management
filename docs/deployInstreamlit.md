 Steps to deploy app using Streamlit Cloud

 Step 1: Create GitHub Repository
   Create a GitHub repository for your application.
   Push all the required files to the repository.

Step 2: Prepare Application Files 
    Ensure you have a requirements.txt file that lists all the libraries required to run the app.
    Include streamlit_app.py containing the Streamlit UI code.


Step 3: Sign Up for Streamlit Cloud
    Go to Streamlit Cloud.
    Sign up using your GitHub account and authorize GitHub.
    Complete all signup steps.

Step 4: Deploy Your App
      Click on "Create app" (top right corner).
      Select "Deploy a public app from GitHub".
      Choose the GitHub repository, the main UI file (stream_app.py), and the Python version.
      set the advanced settings with .env data
            OPENROUTER_API_KEY="your_openrouter_api_key_here"
            MODEL="openai/gpt-4o-mini"
      Click Deploy.    
