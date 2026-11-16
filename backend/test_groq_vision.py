"""Manual provider check; never runs during test collection."""

def main():
    import base64
    import os
    from pathlib import Path
    
    from dotenv import load_dotenv
    from groq import Groq
    
    load_dotenv(Path(__file__).with_name(".env"))
    
    base_dir = Path(__file__).resolve().parent
    image_path = base_dir / "sample_receipt.jpg"
    
    print("Looking for file at:", image_path)
    print("File exists:", image_path.exists())
    
    if not image_path.exists():
        raise FileNotFoundError(f"Receipt image not found at: {image_path}")
    
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    
    encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    
    response = client.chat.completions.create(
        model=os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b"),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Extract the receipt details as JSON with: "
                            "merchant, date, total, currency, category, items. "
                            "Use null for unreadable fields. "
                            "Do not invent values. Return JSON only."
                        )
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{encoded}"
                        }
                    }
                ]
            }
        ],
        max_completion_tokens=2000,
    )
    
    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
