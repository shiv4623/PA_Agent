You have performed a database lookup based on the provider's inputs.
Database Lookup Result:
{{ lookup_result }}

Based strictly on this result, inform the provider about the prior authorization status (include dates if available). 
If no match was found, politely explain that no records match their input.
Finally, ask if there is anything else you can assist them with.

Determine the next node:
- Always return 'end_call'