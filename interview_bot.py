import os
import json
from typing import Dict, List
from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.markdown import Markdown
import colorama
from colorama import Fore, Style

# Initialize colorama
colorama.init()

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize Rich console
console = Console()

class InterviewBot:
    def __init__(self):
        self.interview_types = {
            "1": "Technical Interview",
            "2": "Behavioral Interview",
            "3": "General Interview"
        }
        self.conversation_history = []
        self.system_prompts = {
            "Technical Interview": """You are a technical interviewer conducting a software engineering interview. 
            Focus on technical skills, problem-solving abilities, and coding knowledge. 
            Ask relevant technical questions and provide constructive feedback.""",
            
            "Behavioral Interview": """You are a behavioral interviewer focusing on past experiences, 
            soft skills, and how candidates handle various situations. 
            Ask about specific examples and provide feedback on communication and problem-solving approaches.""",
            
            "General Interview": """You are a general interviewer covering a mix of technical and behavioral questions. 
            Focus on overall fit, career goals, and general problem-solving abilities."""
        }

    def get_interview_type(self) -> str:
        console.print("\n[bold blue]Available Interview Types:[/bold blue]")
        for key, value in self.interview_types.items():
            console.print(f"{key}. {value}")
        
        while True:
            choice = Prompt.ask("\nSelect interview type", choices=list(self.interview_types.keys()))
            return self.interview_types[choice]

    def get_ai_response(self, messages: List[Dict]) -> str:
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            console.print(f"[red]Error getting AI response: {str(e)}[/red]")
            return "I apologize, but I'm having trouble responding right now. Please try again."

    def conduct_interview(self):
        interview_type = self.get_interview_type()
        console.print(f"\n[green]Starting {interview_type}...[/green]")
        
        # Initialize conversation with system prompt
        self.conversation_history = [
            {"role": "system", "content": self.system_prompts[interview_type]},
            {"role": "assistant", "content": "Hello! I'll be conducting your interview today. Let's begin. Could you please introduce yourself?"}
        ]

        console.print(Panel(Markdown(self.conversation_history[-1]["content"]), title="Interviewer"))

        while True:
            # Get user response
            user_input = Prompt.ask("\nYour response")
            
            if user_input.lower() in ['quit', 'exit', 'end']:
                console.print("\n[yellow]Ending interview session...[/yellow]")
                break

            # Add user message to history
            self.conversation_history.append({"role": "user", "content": user_input})

            # Get AI response
            ai_response = self.get_ai_response(self.conversation_history)
            
            # Add AI response to history
            self.conversation_history.append({"role": "assistant", "content": ai_response})
            
            # Display AI response
            console.print(Panel(Markdown(ai_response), title="Interviewer"))

def main():
    console.print("[bold green]Welcome to the Mock Interview Chatbot![/bold green]")
    console.print("This chatbot will help you practice your interview skills.")
    console.print("Type 'quit', 'exit', or 'end' at any time to end the interview.\n")

    bot = InterviewBot()
    bot.conduct_interview()

if __name__ == "__main__":
    main() 