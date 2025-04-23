# Note:
# 1.See the requirements-setup.txt File on How to Set Up Required Packages for the Pothole Reporter Chatbot
# 2.Run the code and open http://127.0.0.1:5000/ to use the chatbot.
# 3.If you want to access http://127.0.0.1:5000/ from your phone to test the chatbot in a mobile environment, you’ll need to make your local server publicly accessible using ngrok. See the file ngrok-instructions.txt in the folder for step-by-step setup instructions.

from flask import Flask, request, jsonify, render_template
from openai import OpenAI
from apikey import OPENAI_API_KEY
import json
import traceback
import os

app = Flask(__name__)
client = OpenAI(api_key=OPENAI_API_KEY)

@app.route("/")
def home():
    return render_template("index.html")

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    print("📨 Incoming /chat payload:", data)
    print("✅ Confirmation:", data.get("reportConfirmed"))

    user_input = data.get("message")
    location = data.get("location")
    location_approved = data.get("locationApproved")
    final_confirmation = data.get("reportConfirmed", False)
    revise_summary = data.get("reviseSummary", False)
    message_history = data.get("history", [])

    gps_line = ""
    if location_approved and location and "lat" in location and "lon" in location:
        gps_line = (
            "The user has approved using GPS. Do NOT mention or display the latitude/longitude coordinates to the user. "
            "Just acknowledge that the user's current location will be used to help locate the pothole."
        )

    if location_approved is None:
        system_prompt = (
            "You are a helpful assistant collecting pothole reports. "
            "Ask: 'Would you like to use your current location as the approximate location of the pothole?' "
            "Do not ask anything else yet."
        )
    elif not final_confirmation and not revise_summary:
        system_prompt = (
            "You are a helpful assistant collecting pothole reports for local governments. "
            f"{gps_line} "
            "Now that location is handled, ask the user to describe the pothole and where it's located. "
            "Say: 'Please describe the pothole, including its location (such as road, direction, nearby landmarks) and any important details (such as size, depth, lane position, or danger it poses).' "
            "Once the user replies, say Here's what I'v got and summarize it like this:\n\n"
            "{\n"
            "  \"location\": \"...\",\n"
            "  \"description\": \"...\"\n"
            "}\n\n"
            "Then ask: 'Does everything look good?'"
        )
    elif revise_summary:
        system_prompt = (
            "You are a helpful assistant updating a pothole report summary. "
            "After the user gives revised information, say Here's the updated information and show the updated report clearly in this format:\n\n"
            "{\n"
            "  \"location\": \"...\",\n"
            "  \"description\": \"...\"\n"
            "}\n\n"
            "This format helps make things easy to read. Do not mention anything technical like JSON or data structures. "
            "After displaying the report, ask: 'Does everything look good?'"
        )
    else:
        system_prompt = (
            "You are a helpful assistant. The user has confirmed the report. "
            "Reply with: 'Your report has been submitted. Thank you for helping us keep our roads safe. Please note that this tool only collects and forwards reports — we cannot guarantee fix timelines or specific outcomes.'"
        )

    messages = [{"role": "system", "content": system_prompt}] + message_history

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages
        )
        reply = response.choices[0].message.content

        if final_confirmation:
            summary_message = ""
            for msg in reversed(message_history):
                if (
                    msg["role"] == "assistant"
                    and "location" in msg["content"].lower()
                    and "description" in msg["content"].lower()
                    and "{" in msg["content"]
                ):
                    summary_message = msg["content"]
                    break


            print("📜 Extracting from message:", summary_message)

            extract_prompt = [
                {
                    "role": "system",
                    "content": (
                        "From the following message, extract and return ONLY a JSON object with keys `location` and `description`. "
                        "Do not include any explanation. Just return valid JSON."
                    )
                },
                {"role": "user", "content": summary_message}
            ]

            extract_response = client.chat.completions.create(
                model="gpt-4",
                messages=extract_prompt
            )
            structured_data_raw = extract_response.choices[0].message.content.strip()

            try:
                structured_data = json.loads(structured_data_raw)
            except json.JSONDecodeError:
                structured_data = {
                    "error": "Failed to parse structured report",
                    "raw": structured_data_raw
                }

            if location and "lat" in location and "lon" in location:
                structured_data["GPS"] = {
                    "Latitude": location.get("lat"),
                    "Longitude": location.get("lon")
                }

            print("📁 Writing to:", os.path.abspath("reports.jsonl"))
            print("📝 Final report content:", structured_data)

            with open("reports.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(structured_data) + "\n")

            return jsonify({
                "reply": reply,
                "structured_report": structured_data
            })

        return jsonify({"reply": reply})

    except Exception as e:
        print("🔥 FULL ERROR in /chat route:")
        traceback.print_exc()
        return jsonify({"error": "Connection error."}), 500

@app.route('/check_intent', methods=['POST'])
def check_intent():
    data = request.json
    user_input = data.get("message")

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a simple yes/no intent classifier. The user was asked to confirm their report or use GPS. Reply only with 'yes' or 'no'."},
                {"role": "user", "content": user_input}
            ]
        )
        reply = response.choices[0].message.content.strip().lower()
        intent = "yes" in reply
        return jsonify({"agreed": intent})

    except Exception as e:
        print("🔥 FULL ERROR in /check_intent route:")
        traceback.print_exc()
        return jsonify({"error": "Connection error."}), 500

if __name__ == "__main__":
    print("📁 reports.jsonl will be saved at:", os.path.abspath("reports.jsonl"))
    app.run(debug=True, use_reloader=False)

