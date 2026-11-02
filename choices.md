What to prioritize: safety and trust, even at the expense of speed or efficiency. Features to that end:
- User checks if this is the correct set of documents to search (can also add more documents)
- Grounding is very clear--easy to see what document and line this was drawn from 
- Security: show how all the tools are open source and hosted with us or smth. log stuff (who approved, model and prompt version)

Back-end choices:
- Read each doc once (task searches not in parallel but sequential--too many questions can overflow context window--less compute though)



ui changes to make:
- make it so that there are quotes? sometimes the answer is directly from the document, but should emphasize it isn't paraphrased
- questions to change should be an expandable section——pretty sure it doesn't matter