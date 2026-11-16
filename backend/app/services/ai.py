"""Groq adapter: bounded requests, no tools, no credential/prompt logging."""
import json
from fastapi import HTTPException
from groq import Groq, APIError, APITimeoutError, RateLimitError
from app.core.config import get_settings


def complete(content, instructions, schema=None, history=None):
    settings=get_settings()
    model=settings.GROQ_VISION_MODEL if schema else settings.GROQ_CHAT_MODEL
    if not settings.GROQ_API_KEY or not model:
        raise HTTPException(503,'AI is not available yet. Provider configuration is incomplete.')
    parts=[]
    for part in content:
        if part['type']=='input_text': parts.append({'type':'text','text':part['text']})
        elif part['type']=='input_image': parts.append({'type':'image_url','image_url':{'url':part['image_url']}})
    if schema:
        instructions+=' Return a JSON object matching this schema. Unreadable fields must be null. '+json.dumps(schema)
    messages=[{'role':'system','content':instructions}]
    for row in (history or [])[-6:]:
        messages.extend([{'role':'user','content':row['question'][:2000]},{'role':'assistant','content':row['answer'][:6000]}])
    messages.append({'role':'user','content':parts})
    try:
        client=Groq(api_key=settings.GROQ_API_KEY,timeout=45.0,max_retries=0)
        try:
            options={'response_format':{'type':'json_object'}} if schema else {}
            response=client.chat.completions.create(model=model,messages=messages,max_completion_tokens=2500 if schema else 1800,**options)
        finally:
            client.close()
        choice=response.choices[0]
        answer=choice.message.content
        if choice.finish_reason!='stop' or not answer or not answer.strip():
            raise ValueError('Incomplete provider output')
        return answer
    except RateLimitError:
        raise HTTPException(503,'AI provider rate limit reached. Please retry shortly; no successful usage credit was charged.') from None
    except APITimeoutError:
        raise HTTPException(504,'AI provider timed out. No successful usage credit was charged.') from None
    except (APIError,ValueError,KeyError,IndexError,TypeError):
        raise HTTPException(502,'AI provider could not complete this request. No successful usage credit was charged.') from None
