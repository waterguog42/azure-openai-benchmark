# Request generator
# 
# This module is reponsible for generate the request sent over to OpenAI. 

import wonderwords
import time
import math

from .oaitokenizer import num_tokens_from_messages

CACHED_PROMPT=""
CACHED_MESSAGES_TOKENS=0

def _generate_messages(model:str, tokens:int, max_tokens:int=None) -> ([dict], int):
   """
   Generate `messages` array based on tokens and max_tokens.
   Returns Tuple of messages array and actual context token count.
   """
   global CACHED_PROMPT
   global CACHED_MESSAGES_TOKENS
   try:
      r = wonderwords.RandomWord()
      messages = [{"role":"user", "content":str(time.time()) + " "}]
      if max_tokens is not None:
         messages.append({"role":"user", "content":str(time.time()) + f" write a long essay about life in at least {max_tokens} tokens"})
      messages_tokens = 0

      if len(CACHED_PROMPT) > 0:
         messages[0]["content"] += CACHED_PROMPT
         messages_tokens = CACHED_MESSAGES_TOKENS
      else:
         prompt = ""
         base_prompt = messages[0]["content"]
         while True:
            messages_tokens = num_tokens_from_messages(messages, model)
            remaining_tokens = tokens - messages_tokens
            if remaining_tokens <= 0:
               break
            prompt += " ".join(r.random_words(amount=math.ceil(remaining_tokens/4))) + " "
            messages[0]["content"] = base_prompt + prompt

         CACHED_PROMPT = prompt
         CACHED_MESSAGES_TOKENS = messages_tokens

   except Exception as e:
      print (e)

   return (messages, messages_tokens)

class RequestGenerator:
   def getRequest():
      return ''
#
class RandomGenerator(RequestGenerator):
   def __init__(self, size:int):
      return
   
    def getRequest():

# predefined generator uses the files precreated in a pth
class PredefinedGenerator(RequestGenerator):

   def __init__(self, path:str):
      return
