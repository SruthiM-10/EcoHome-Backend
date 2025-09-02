# Thermostat Backend API

This is a secure FastAPI backend for a thermostat control application. It features a complete user authentication system and is designed to be deployed on Railway. The backend provides the necessary foundation for integrating with Google's Smart Device Management (SDM) API to control real-world Nest thermostats.

## ✨ Key Features

* **User Registration:** Secure endpoint for new user creation.
* **Email Verification:** New users receive a verification email to activate their account.
* **JWT Authentication:** Protected endpoints using JSON Web Tokens.
* **Password Hashing:** Passwords are securely hashed using `bcrypt`.
* **Database Integration:** Uses PostgreSQL with SQLAlchemy ORM.
* **Ready for SDM:** Includes the foundation for adding Google OAuth 2.0 flow to connect with Nest devices.

## 🛠️ Tech Stack

* **Backend:** FastAPI
* **Database:** PostgreSQL
* **ORM:** SQLAlchemy
* **Authentication:** Passlib (for hashing), python-jose (for JWT)
* **Hosting:** Railway

***

## 🚀 Deployment to Railway

These instructions will guide you through deploying the application on a free Railway account.

### 1. Code Preparation

Before pushing your code to GitHub, ensure you have the following files in your project's root directory.

* **`requirements.txt`**: A list of all Python dependencies. You can generate it with:
    ```bash
    pip freeze > requirements.txt
    ```

* **`Procfile`**: This tells Railway how to start the web server. Create a file named `Procfile` with this exact content:
    ```
    web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    ```

* **`.gitignore`**: Make sure your `.env` file is included in your `.gitignore` to keep secrets out of the repository.
    ```gitignore
    # .gitignore
    __pycache__/
    .env
    *.pyc
    ```

After creating these files, commit and push your code to a new GitHub repository.

### 2. Railway Project Setup

1.  **Create a Railway Account:** Sign up at [railway.app](https://railway.app) using your GitHub account.
2.  **Create New Project:** From the dashboard, start a new project.
3.  **Provision PostgreSQL Database:**
    * In your project, click **New** -> **Database** -> **Add PostgreSQL**.
    * Once created, click on the Postgres service, go to the **Connect** tab, and copy the `DATABASE_URL`. You will need this in the next step.
4.  **Deploy from GitHub:**
    * Go back to the project dashboard, click **New** -> **GitHub Repo**.
    * Configure the GitHub App to grant Railway access to your repository.
    * Select your project's repository. Railway will automatically start building it.

### 3. Environment Variable Configuration

The initial deployment will likely fail. You must now add your environment variables.

1.  Click on the `web` service that Railway created for your application.
2.  Go to the **Variables** tab.
3.  Add all the variables from your local `.env` file. Refer to the table below for guidance.

| Variable Name                | Value / Description                                                                                             |
| :--------------------------- | :-------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URL`               | Paste the URL you copied from the **Connect** tab of your Railway Postgres service.                             |
| `BACKEND_BASE_URL`           | Go to the **Settings** tab of your `web` service, copy the public domain, and add `https://` to the front.         |
| `SECRET_KEY`                 | Your long, random secret string for JWT signing.                                                                |
| `ALGORITHM`                  | `HS256`                                                                                                         |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| `60`                                                                                                            |
| `SMTP_HOST`                  | e.g., `smtp.gmail.com`                                                                                          |
| `SMTP_PORT`                  | e.g., `587`                                                                                                     |
| `SMTP_USER`                  | Your email address for sending verification emails.                                                             |
| `SMTP_PASS`                  | Your email application-specific password.                                                                       |
| `SMTP_FROM`                  | The "From" address for emails, e.g., `"Your App <you@example.com>"`                                             |

### 4. Finalizing and Testing

After you add the variables, Railway will automatically trigger a new deployment. Once the deployment status shows as **ACTIVE**, your API is live.

You can test all the endpoints by visiting your public URL and adding `/docs` to the end:
`https://your-app-name.up.railway.app/docs`

***

## 📋 API Endpoints

| Method | Endpoint        | Description                                       |
| :----- | :-------------- | :------------------------------------------------ |
| `POST` | `/auth/register`  | Creates a new user and sends a verification email. |
| `GET`  | `/auth/verify`    | Verifies a user's email via a token from the email. |
| `POST` | `/auth/login`     | Authenticates a user and returns a JWT access token. |
