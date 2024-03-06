# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
import math
import os
import sys
import time
from typing import Iterable, Iterator

import aiohttp
import wonderwords

from .asynchttpexecuter import AsyncHTTPExecuter
from .oairequester import OAIRequester
from .oaitokenizer import num_tokens_from_messages
from .ratelimiting import NoRateLimiter, RateLimiter
from .statsaggregator import _StatsAggregator
from .requestbuilder import _FileRequestBuilder, _RequestBuilder
from .requestbuilder import _RandomRequestBuilder

def load(args):
   try:
        _validate(args)
   except ValueError as e:
       print(f"invalid argument(s): {e}")
       sys.exit(1)

   api_key = os.getenv(args.api_key_env)
   url = args.api_base_endpoint[0] + "/openai/deployments/" + args.deployment + "/chat/completions"
   url += "?api-version=" + args.api_version

   rate_limiter = NoRateLimiter()
   if args.rate is not None and args.rate > 0:
      rate_limiter = RateLimiter(args.rate, 60)

   max_tokens = args.max_tokens
   context_tokens = args.context_tokens
   if args.shape_profile == "balanced":
      context_tokens = 500
      max_tokens = 500
   elif args.shape_profile == "context":
      context_tokens = 2000
      max_tokens = 200
   elif args.shape_profile == "generation":
      context_tokens = 500
      max_tokens = 1000

   logging.info(f"using shape profile {args.shape_profile}: context tokens: {context_tokens}, max tokens: {max_tokens}")


   logging.info("starting load...")

   # create the request builder
   if (args.request_path is not None):
      request_builder = _FileRequestBuilder(args.request_path)
   else:
      request_builder = _RandomRequestBuilder("gpt-4-0613", context_tokens,
         max_tokens=max_tokens,
         completions=args.completions,
         frequency_penalty=args.frequency_penalty,
         presence_penalty=args.presence_penalty,
         temperature=args.temperature,
         top_p=args.top_p)

   # run the load
   _run_load(request_builder,
      max_concurrency=args.clients, 
      api_key=api_key,
      url=url,
      rate_limiter=rate_limiter,
      backoff=args.retry=="exponential",
      request_count=args.requests,
      duration=args.duration,
      aggregation_duration=args.aggregation_window,
      json_output=args.output_format=="jsonl",
      stream=not args.non_stream)

def _run_load(request_builder: Iterable[dict],
              max_concurrency: int, 
              api_key: str,
              url: str,
              rate_limiter=None, 
              backoff=False,
              duration=None, 
              aggregation_duration=60,
              request_count=None,
              json_output=False,
              stream=True):
   aggregator = _StatsAggregator(
      window_duration=aggregation_duration,
      dump_duration=1, 
      clients=max_concurrency,
      json_output=json_output)
   requester = OAIRequester(api_key, url, backoff=backoff, stream=stream)

   async def request_func(session:aiohttp.ClientSession):
      nonlocal aggregator
      nonlocal requester
      request_body, messages_tokens = request_builder.__next__()
      aggregator.record_new_request()
      stats = await requester.call(session, request_body)
      stats.context_tokens = messages_tokens
      try:
         aggregator.aggregate_request(stats)
      except Exception as e:
         print(e)

   executer = AsyncHTTPExecuter(
      request_func, 
      rate_limiter=rate_limiter, 
      max_concurrency=max_concurrency)

   aggregator.start()
   executer.run(
      call_count=request_count, 
      duration=duration)
   aggregator.stop()

   logging.info("finished load test")

def _validate(args):
    if len(args.api_version) == 0:
      raise ValueError("api-version is required")
    if len(args.api_key_env) == 0:
       raise ValueError("api-key-env is required")
    if os.getenv(args.api_key_env) is None:
       raise ValueError(f"api-key-env {args.api_key_env} not set")
    if args.clients < 1:
       raise ValueError("clients must be > 0")
    if args.requests is not None and args.requests < 0:
       raise ValueError("requests must be > 0")
    if args.duration is not None and args.duration != 0 and args.duration < 30:
       raise ValueError("duration must be > 30")
    if args.rate is not None and  args.rate < 0:
       raise ValueError("rate must be > 0")
    if args.shape_profile == "custom":
       if args.context_tokens < 1:
          raise ValueError("context-tokens must be specified with shape=custom")
    if args.max_tokens is not None and args.max_tokens < 0:
       raise ValueError("max-tokens must be > 0")
    if args.completions < 1:
       raise ValueError("completions must be > 0")
    if args.frequency_penalty is not None and (args.frequency_penalty < -2 or args.frequency_penalty > 2):
       raise ValueError("frequency-penalty must be between -2.0 and 2.0")
    if args.presence_penalty is not None and (args.presence_penalty < -2 or args.presence_penalty > 2):
       raise ValueError("presence-penalty must be between -2.0 and 2.0")
    if args.temperature is not None and (args.temperature < 0 or args.temperature > 2):
       raise ValueError("temperature must be between 0 and 2.0")
    