# IOSXE Chatbot

IOSXE Chatbot is a terminal-based tool that integrates Cisco's pyATS/Genie testbed automation framework with OpenAI's GPT-4o large language model. It allows network engineers to interact conversationally with Cisco IOS-XE devices via CLI, enabling smart querying, command execution, and automated response parsing using LLM-generated JSON outputs.

## Features

- Interactively ask network questions and receive structured JSON responses
- Automatically run Cisco IOS-XE commands or apply configurations based on LLM decisions
- Full OpenAI API integration using the `responses` feature with `gpt-4o`
- Menu-based and prompt-driven input with command handling (`/m`, `/c`, `/p`, `/q`, etc.)
- Built-in Genie testbed loading and connection management
- Token usage tracking for cost awareness
- JSON-formatted output for consistent parsing and automation

## Installation

1. **Clone the Repository**

```bash
git clone https://github.com/splitnines/iosxe_chatbot.git
cd iosxe_chatbot
```

2. **Set up Python Environment**

We recommend using a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. **Install Dependencies**

```bash
pip install -r requirements.txt
```

4. **Set OpenAI API Key**

Export your OpenAI API key:

```bash
export OPENAI_API_KEY=your_openai_api_key_here
```

5. **Prepare Your Testbed**

Place a `testbed.yaml` file in the project root, configured with your Cisco IOS-XE device credentials and connection details.

6. **Run the Chatbot**

```bash
python iosxe_chatbot.py
```

## Usage Notes

- Ensure the `iosxe_prompt.md` file is present and contains the system prompt for the LLM.
- Supported user escape commands:
  - `/m` — Show menu
  - `/p` — Show prompt
  - `/r` — Reload prompt
  - `/c <command>` — Run a CLI command directly
  - `/n` — Start new LLM context window
  - `/q` — Quit session

## Example Interaction

```text
┌──(0)-[sr1-1]-[IOS-XE Chatbot]
└─$ What is the IP address of interface GigabitEthernet1?

{"command": ["show ip interface brief"]}

{"answer": "IP address 10.1.100.3 is assigned to interface GigabitEthernet1"}
```

## Acknowledgements

- **Cisco Systems**: For the powerful [pyATS](https://developer.cisco.com/pyats/) and Genie frameworks.
- **OpenAI**: For providing access to the GPT-4o model via API.
- **Open Source Community**: For the Python ecosystem and all packages used in this project.

## License

This project is licensed under the terms described in the `LICENSE` file.

---

