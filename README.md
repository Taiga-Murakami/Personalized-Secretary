# AI Secretary System (Slack Socket Mode x Gemini)

A fully autonomous, private AI secretary system powered by Slack Socket Mode and the Google Gemini API.
This system seamlessly handles everything from automatically collecting and delivering daily news/market data to holding context-aware natural language conversations.

## 🚀 Key Features

- **Automated Morning Reports (Push)**: Fetches US/Japan/China market trends, major news via RSS, and tech exhibition schedules every morning, and delivers them to Slack with AI-generated insights.
- **Context-Aware Conversations (Pull)**: Reply to the delivered news via Slack threads to dive deeper into the topics. The AI perfectly remembers the context of the thread.
- **Beautiful Slack UI**: Automatically converts standard Markdown into Slack's native rich UI (Block Kit) for highly readable reports.
- **Dynamic Channel Personas**: Switches the AI's persona (e.g., Economics Research Assistant, Business Consultant) dynamically based on the Slack channel.
- **Google Calendar Integration**: Connects with Google Calendar to automatically fetch upcoming schedules from both your main and AI-dedicated accounts, and supports seamless event creation directly from Slack using Gemini's Function Calling.

## 🏗️ System Architecture

Designed with a strong emphasis on maintainability and scalability, featuring a loosely coupled architecture.

- **Infrastructure**: Fully containerized with Docker and Docker Compose.
- **Secure Communication**: Utilizes Slack Socket Mode (`slack_bolt`). No public endpoints or Webhook URLs are exposed.
- **Asynchronous Scheduler**: Employs `APScheduler` to run background jobs without blocking the Socket Mode event loop.
- **Loosely Coupled Modules**: Data collection (`bot_broadcast/`), report generation (`report_generator.py`), and UI formatting (`slack_formatter.py`) are strictly separated from the main entry point.

## 📁 Directory Structure

```text
.
├── bot_broadcast/            # Data collection modules
│   ├── fetch_market.py       # Fetches market & forex data
│   ├── fetch_news.py         # Fetches news from major RSS feeds
│   └── fetch_tech.py         # Scrapes tech exhibition schedules
├── settings/                 # Configuration files
│   ├── .env.example          # Environment variables template
│   └── contexts.example.json # Channel-specific prompt settings
├── main.py                   # Application entry point
├── report_generator.py       # Report generation logic via Gemini
├── slack_formatter.py        # Markdown to Slack Block Kit converter
├── Dockerfile               
├── docker-compose.yml       
└── requirements.txt
```

## 🛠️ Setup Instructions
**1. Clone the Repository**
```bash
git clone [https://github.com/Taiga-Murakami/mySecretary.git](https://github.com/Taiga-Murakami/mySecretary.git)
cd your-repo-name
```

**2. Configure Environment Variables**
Copy the template files in the ```settings``` directory and insert your own API keys.
```bash
cp settings/.env.example settings/.env
cp settings/contexts.example.json settings/contexts.json
```

Required API Keys in ```.env```:
 - ```SLACK_BOT_TOKEN``` (Starts with xoxb-)
 - ```SLACK_APP_TOKEN``` (Starts with xapp-)
 - ```GEMINI_API_KEY``` 
 - ```NOTION_API_KEY``` (Optional: for local memory storage)

**3. Run with Docker**
```bash
docker compose up -d --build
```
Check the logs with ```docker compose logs -f```. If you see ```Background Scheduler has started.``` and ```AI Secretary is running in Socket Mode!```, the setup is complete.


## 🎨 Customization Guide
This system is highly modular. You can easily customize it to build your own perfect AI secretary without touching the core ```main.py``` logic.

**1. Adding/Editing Data Sources**
To add a new data source (e.g., weather forecasts or specific blogs), simply create a new script (e.g., ```fetch_weather.py```) inside the ```bot_broadcast/``` directory. Ensure it has a ```get_data() -> str``` function, and then import it into ```report_generator.py```.

**2. Adding Custom Slack Channels**
You can deploy different AI personas to different Slack channels.
1. Add a new channel ID to your ```.env``` (e.g., ```SLACK_CHANNEL_NEW=C12345678```).
2. Open ```settings/contexts.json``` and add a new block under ```"CHANNELS"``` with your desired ```"role_name"``` and ```"system_prompt"```. The system will automatically apply this persona when you chat in that channel.

**3. Modifying AI Prompts & Formatting**
If you want to change the tone of the morning report or adjust its layout, edit the ```sys_prompt``` inside ```report_generator.py```. The system uses Few-Shot prompting, so providing a clear output example in the prompt is highly recommended.

**Note** that all comments and outputs are written in Japanese, so customize into your own language for easily understanding. 

**4. Google Calendar Connection (Account A & Account B)**
The system supports multi-account calendar aggregation using two distinct Google accounts for enhanced privacy and security:

- **Account A (Main Account)**: Your personal or corporate primary Google account. The system only *reads* schedules from this account to display your upcoming events, ensuring your primary calendar remains safe from accidental modifications.
- **Account B (AI Account)**: A dedicated Google account created specifically for this AI secretary system. The system has full permissions to both *read* schedules and *write* (create new events) on this account.

**How to Setup:**
1. **Generate Credentials**: Go to the Google Cloud Console using your **AI Account (Account B)**, enable the Google Calendar API, create OAuth 2.0 credentials, and download the `credentials.json` file.
2. **Authorize the App**: Run the authentication flow locally to generate the `token.json` file. Place this `token.json` into your project root directory (ensure it is listed in `.gitignore`).
3. **Share Calendar**: Open your **Main Account (Account A)** Google Calendar settings, and share your calendar with the AI Account's email address, granting at least "See all event details" permissions.
4. **Configure Environment Variables**: Add your Main Account's email to your `settings/.env` file:
   ```env
   ACCOUNT_A_EMAIL=your-main-account-email@gmail.com

## 🔧 Technologies Used
- Python 3.11
- Docker / Docker Compose
- ```slack_bolt```, ```slack_sdk``` (Slack API / Socket Mode)
- ```google-genai``` (Gemini API)
- ```apscheduler```
- ```beautifulsoup4```

## 📝 License
This project is licensed under the MIT License.