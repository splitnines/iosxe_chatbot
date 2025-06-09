import openai
import os


def prompt_gpt(prompt):
    openai.api_key = os.getenv("OPENAI_API_KEY")

    uploaded_file = openai.files.create(
        file=open("sr1-1_running-config.pdf", "rb"),
        purpose="assistants",
    )

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt,
                    },
                    {"type": "file", "file": {"file_id": uploaded_file.id}},
                ],
            }
        ],
    )

    return response


def get_prompt(filename):
    with open(filename, "r") as f:
        prompt = f.read()
    return prompt


def main():
    response = prompt_gpt(get_prompt("prompt.txt"))

    print(f"{response}\n\n")
    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
