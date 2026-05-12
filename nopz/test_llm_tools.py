import os

import llm


def get_current_weather(location: str, unit: str = "fahrenheit") -> str:
    """
    Get the current weather in a given location.

    :param location: The city and state, e.g., San Francisco, CA
    :param unit: The unit of temperature to return, e.g., fahrenheit or celsius
    """
    print(f"\n[TOOL CALLED] get_current_weather(location='{location}', unit='{unit}')")
    if "Paris" in location:
        return f"The weather in {location} is 65 degrees {unit} and raining."
    return f"The weather in {location} is 72 degrees {unit} and sunny."


def calculate_math(expression: str) -> str:
    """
    Evaluate a simple mathematical expression.

    :param expression: The math expression to evaluate, e.g., "2 + 2"
    """
    print(f"\n[TOOL CALLED] calculate_math(expression='{expression}')")
    try:
        result = eval(expression, {"__builtins__": {}})
        return str(result)
    except Exception as e:
        return f"Error evaluating expression: {e}"


def main():
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(
            "Warning: GOOGLE_API_KEY or GEMINI_API_KEY environment variable is not set."
        )
        print("You may need to export one of these for the model to work.")

    # The llm-gemini plugin registers models like 'gemini-1.5-pro-latest'
    # We try a few common aliases/names that might be available
    model_name = "gemini-1.5-pro-latest"
    try:
        model = llm.get_model(model_name)
    except llm.UnknownModelError:
        print(f"Model '{model_name}' not found. Falling back to default Gemini model.")
        model = llm.get_model("gemini-1.5-flash-latest")

    if api_key:
        model.key = api_key

    print(f"=== Testing llm library tools with {model.model_id} ===")

    tools_to_use = [get_current_weather, calculate_math]

    # We can use a conversation to keep context
    conversation = model.conversation()

    # Test 1: Weather tool
    prompt1 = "What is the weather like in Paris right now?"
    print(f"\nUser: {prompt1}")
    response1 = conversation.prompt(prompt1, tools=tools_to_use)
    print(f"Model: {response1.text()}")

    # Test 2: Math tool
    prompt2 = "If I multiply the temperature in Paris by 3.5, what do I get?"
    print(f"\nUser: {prompt2}")
    response2 = conversation.prompt(prompt2, tools=tools_to_use)
    print(f"Model: {response2.text()}")

    # Test 3: Multiple tools or reasoning
    prompt3 = "What is the weather in Tokyo, and what is 1024 divided by 8?"
    print(f"\nUser: {prompt3}")
    response3 = conversation.prompt(prompt3, tools=tools_to_use)
    print(f"Model: {response3.text()}")


if __name__ == "__main__":
    main()
