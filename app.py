from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import openai
import os
from dotenv import load_dotenv
import asyncio
import aiohttp

# Load environment variables
load_dotenv()

app = Flask(__name__)
# Configure CORS for production - you may want to restrict this to specific domains
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize OpenAI client
openai.api_key = os.getenv("OPENAI_API_KEY")

# Interview types and their system prompts
INTERVIEW_TYPES = {
    "technical": (
        "You are a human interviewer conducting a real software engineering interview. "
        "Only ask one concise, relevant technical question at a time. Wait for the candidate's answer before moving on. "
        "Never explain, never give advice, never answer as the candidate, and never break character. "
        "Stay in character as the interviewer for the entire conversation."
    ),
    "behavioral": (
        "You are a human interviewer conducting a behavioral interview. "
        "Only ask one concise, relevant behavioral or situational question at a time. Wait for the candidate's answer before moving on. "
        "Never explain, never give advice, never answer as the candidate, and never break character. "
        "Stay in character as the interviewer for the entire conversation."
    ),
    "general": (
        "You are a human interviewer conducting a general job interview. "
        "Only ask one concise, relevant question at a time. Wait for the candidate's answer before moving on. "
        "Never explain, never give advice, never answer as the candidate, and never break character. "
        "Stay in character as the interviewer for the entire conversation."
    )
}

def build_system_prompt(interview_type, job_background):
    base_prompt = INTERVIEW_TYPES.get(interview_type, INTERVIEW_TYPES['general'])
    job_title = job_background.get('jobTitle', '') if job_background else ''
    job_desc = job_background.get('jobDesc', '') if job_background else ''
    if job_title or job_desc:
        return f"{base_prompt}\n\nJob Title: {job_title}\nJob Description: {job_desc}\nUse this background to tailor your questions and feedback."
    return base_prompt

def get_focused_job_description(job_background, interview_type):
    title = job_background.get('jobTitle', '').strip()
    desc = job_background.get('jobDesc', '').strip()
    if desc:
        return desc
    # Provide a default/focused description based on title and type
    if interview_type == 'technical':
        return f"As a {title}, you are responsible for designing, developing, and maintaining software solutions, collaborating with team members, and solving technical challenges."
    elif interview_type == 'behavioral':
        return f"As a {title}, you are expected to demonstrate strong communication, teamwork, and problem-solving skills in a professional environment."
    else:
        return f"As a {title}, you are expected to contribute to the company's goals and culture, adapting to various challenges and responsibilities."

@app.route('/api/interview-types', methods=['GET'])
def get_interview_types():
    return jsonify(list(INTERVIEW_TYPES.keys()))

@socketio.on('start_interview')
def handle_start_interview(data):
    interview_type = data.get('type', 'general')
    job_background = data.get('jobBackground', {})
    system_prompt = build_system_prompt(interview_type, job_background)
    # Initialize conversation
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "assistant", "content": "Hello! I'll be conducting your interview today. Let's begin. Could you please introduce yourself?"}
    ]
    emit('interviewer_message', {'message': messages[-1]['content']})
    # Optionally, store initial messages in session or state if needed

@socketio.on('user_message')
def handle_user_message(data):
    try:
        messages = data.get('conversation_history', [])
        job_background = data.get('job_background', {})
        interview_type = data.get('interview_type', 'general')
        # Always ensure system prompt is at the start
        if not messages or messages[0].get('role') != 'system':
            system_prompt = build_system_prompt(interview_type, job_background)
            messages = [{"role": "system", "content": system_prompt}] + messages
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        ai_response = response.choices[0].message.content
        emit('interviewer_message', {'message': ai_response})
    except Exception as e:
        emit('error', {'message': str(e)})

async def fetch_sample_answer(session, api_key, job_title, focused_desc, question):
    prompt = (
        f"You are a candidate interviewing for the following job: {job_title}. "
        f"Here is the job description: {focused_desc}.\n\n"
        f"Given the question below, provide a realistic, concise, and relevant answer as if you are a candidate for this job. "
        "Focus on the question and the job description. Never break character.\n\n"
        f"Question: {question}\nYour answer:"
    )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "system", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 180
    }
    async with session.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers) as resp:
        data = await resp.json()
        return data['choices'][0]['message']['content']

@socketio.on('end_interview')
def handle_end_interview(data):
    try:
        conversation = data.get('conversation_history', [])
        job_background = data.get('job_background', {})
        interview_type = data.get('interview_type', 'general')
        qas = data.get('questions_and_answers', [])
        # 1. Suggestions for improvement (short, actionable, human)
        suggestions_prompt = (
            "You are an expert interview coach. Given the following interview transcript, provide 2-3 short, actionable, and friendly tips for the candidate to improve their answers and performance. "
            "Be brief and specific, not generic or verbose. Only give tips, never answer the questions or break character.\n\n"
            f"Job Title: {job_background.get('jobTitle', '')}\nJob Description: {get_focused_job_description(job_background, interview_type)}\n\nTranscript:\n"
            + '\n'.join([f"{turn['role']}: {turn['content']}" for turn in conversation])
        )
        suggestions_resp = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "system", "content": suggestions_prompt}],
            temperature=0.7,
            max_tokens=200
        )
        suggestions = suggestions_resp.choices[0].message.content
        # 2. Sample answers for each question (parallel)
        focused_desc = get_focused_job_description(job_background, interview_type)
        questions = [qa['question'] for qa in qas if qa.get('question') and qa.get('answer')]
        user_answers = [qa['answer'] for qa in qas if qa.get('question') and qa.get('answer')]
        job_title = job_background.get('jobTitle', '')
        api_key = os.getenv("OPENAI_API_KEY")
        async def gather_samples():
            async with aiohttp.ClientSession() as session:
                tasks = [fetch_sample_answer(session, api_key, job_title, focused_desc, q) for q in questions]
                return await asyncio.gather(*tasks)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        sample_answers = loop.run_until_complete(gather_samples())
        comparisons = []
        for i, question in enumerate(questions):
            comparisons.append({
                'question': question,
                'user_answer': user_answers[i],
                'sample_answer': sample_answers[i]
            })
        # 3. Return summary
        emit('interview_summary', {
            'transcript': conversation,
            'suggestions': suggestions,
            'comparisons': comparisons
        })
    except Exception as e:
        emit('error', {'message': str(e)})

@app.route('/')
def serve_index():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5050))
    host = os.getenv('HOST', 'localhost')
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    socketio.run(app, debug=debug, port=port, host=host) 