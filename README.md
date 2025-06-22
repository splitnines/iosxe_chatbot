# Cisco IOS-XE Chatbot with OpenAI GPT

This project implements an interactive chatbot that interfaces with Cisco IOS-XE routers and switches using natural language queries. It leverages the OpenAI GPT API (via the `openai` Python client) and Cisco pyATS for command execution and configuration. The assistant is prompt-engineered to strictly return JSON-based responses that your Python program can parse and act on.

---

## Features

- Query IOS-XE device status in natural language  
- Automatically runs `show` commands and returns results  
- Supports generating and applying configuration commands  
- All LLM interactions are done using OpenAI's GPT-4o model  
- Conversation context is preserved until reset with `/new`

---

## Requirements

- Python 3.9+
- Cisco pyATS and Unicon
- OpenAI Python SDK
- A valid OpenAI API key
- A testbed YAML file for your IOS-XE device (`testbed.yaml`)

Install dependencies:

```bash
pip install -r requirements.txt
```

Example `requirements.txt`:

```
genie
unicon
openai
```

---

## Setup

1. Place your Cisco testbed definition in a file named `testbed.yaml`.
2. Ensure `cisco_iosxe_prompt.md` is present in the same directory.
3. Set your OpenAI API key:

```bash
export OPENAI_API_KEY="sk-..."
```

---

## Usage

Run the chatbot:

```bash
python iosxe_chatbot.py
```

### Available Commands

- `/new` — Start a new chat session (resets context)
- `/menu` — Show help menu
- `/prompt` — Print the current system prompt used for the LLM

### Example Interaction

```
[0]Prompt: What is the IP address of GigabitEthernet1?
```

LLM response:

```json
{"command": ["show ip interface brief"]}
```

After device command execution, it continues:

```json
{"answer": "IP address 10.1.100.3 is assigned to interface GigabitEthernet1"}
```

---

## File Structure

- `iosxe_chatbot.py` — Main CLI chat interface
- `cisco_iosxe_prompt.md` — System prompt to guide the LLM
- `testbed.yaml` — Cisco pyATS device definition file

---

## Notes

- The device in your testbed file should be named `sr1-1`.
- The chatbot only accepts valid JSON responses (`command`, `configure`, or `answer`).
- Token usage for the session is logged at the end.

---

## License

MIT License