from agent import run_agent


print("CodeMate started!")
print("Type 'exit' to quit.\n")


while True:

    user_input = input("You: ")

    if user_input.lower() == "exit":

        print("CodeMate: Bye!")

        break

    run_agent(user_input)