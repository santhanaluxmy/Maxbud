"""Manual provider check; never runs during test collection."""

def main():
    
    import os
    from pathlib import Path
    
    from dotenv import load_dotenv
    from groq import Groq
    
    # Load existing backend environment settings.
    load_dotenv(Path(__file__).with_name(".env"))
    
    api_key = os.getenv("GROQ_API_KEY")
    model = os.getenv("GROQ_CHAT_MODEL", "openai/gpt-oss-20b")
    
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is missing in backend/.env")
    
    client = Groq(api_key=api_key, timeout=30.0)
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are MaxBud, a friendly budget assistant."
            },
            {
                "role": "user",
                "content": "Say hello to MaxBud in one short sentence."
            }
        ],
        max_completion_tokens=150,
    )
    
    print("Groq API connection successful!")
    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
