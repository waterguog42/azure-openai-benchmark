import json
import logging
import os
import wonderwords
import time
import math

from typing import Iterable, Iterator
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

class _RequestBuilder:
   """
   Wrapper iterator class to build request payloads.
   """
   def __iter__(self) -> Iterator[dict]:
      return self

   def __next__(self) -> (dict, int):
      return {}, 0

class _RandomRequestBuilder(_RequestBuilder):
   def __init__(self, model:str, context_tokens:int,
                max_tokens:None, 
                completions:None, 
                frequency_penalty:None, 
                presence_penalty:None, 
                temperature:None, 
                top_p:None):
      self.model = model
      self.context_tokens = context_tokens
      self.max_tokens = max_tokens
      self.completions = completions
      self.frequency_penalty = frequency_penalty
      self.presence_penalty = presence_penalty
      self.temperature = temperature
      self.top_p = top_p

      logging.info("warming up prompt cache")
      _generate_messages(self.model, self.context_tokens, self.max_tokens)

   def __iter__(self) -> Iterator[dict]:
      return self

   def __next__(self) -> (dict, int):
      messages, messages_tokens = _generate_messages(self.model, self.context_tokens, self.max_tokens)
      body = {"messages":messages}
      if self.max_tokens is not None:
         body["max_tokens"] = self.max_tokens
      if self.completions is not None:
         body["n"] = self.completions
      if self.frequency_penalty is not None:
         body["frequency_penalty"] = self.frequency_penalty
      if self.presence_penalty is not None:
         body["presence_penalty"] = self.presence_penalty
      if self.temperature is not None:
         body["temperature"] = self.temperature
      if self.top_p is not None:
         body["top_p"] = self.top_p
      return body, messages_tokens

# generate request based on file
class _FileRequestBuilder(_RequestBuilder):
   requests = []
   count = 0

   def __init__(self, path:str):
      self.path = path
      files = os.listdir(path)
      for i in files:
         if not i.endswith(".json"):
               continue
         with open(os.path.join(path, i), 'r') as f:
            try :
               json_data = f.read()
               data = json.loads(json_data)
               self.requests.append(data)
            except json.JSONDecodeError as x:
               print(f'Error in file {i} : {x}')
               exit

      print(f'json requests found: {self.requests.__len__()}')

   def __iter__(self) -> Iterator[dict]:
      return self

   def __next__(self) -> (dict, int):
      index = self.count % self.requests.__len__()
      ret = self.requests[index]
      self.count += 1
      return ret, 0