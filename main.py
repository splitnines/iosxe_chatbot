import openai
import os


def prompt_gpt(prompt):
    openai.api_key = os.getenv("OPENAI_API_KEY")

    file = openai.files.create(
        file=open("sr1-1_running-config.pdf", "rb"),
        purpose="user_data",
    )

    response = openai.responses.create(
        model="gpt-4o",
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "file_id": file.id,
                    },
                    {
                        "type": "input_text",
                        "text": prompt,
                    },
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
    response = prompt_gpt(get_prompt("prompt4.txt"))

    print(response.output_text)


if __name__ == "__main__":
    main()
