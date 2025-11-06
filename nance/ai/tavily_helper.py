from typing import Any


from langchain.tools import tool
from langchain_community.tools.tavily_search import TavilySearchResults

class TavilyHelper:
    def __init__(self):
        self.search_tool = TavilySearchResults(k=1)

    def handle_web_search(self, merchant: str) -> str:
        try:
            query = f"About {merchant} company"
            result = self.search_tool.run(query)
            print("Tavily search result Done ✅")
            top_k_contents = self.get_top_k_contents(result)
            formatted_context = self.format_context(top_k_contents)
            return formatted_context
        except Exception as e:
            raise e

    def trim_content(self, text: str, max_words: int = 150) -> str:
        return " ".join(text.strip().split()[:max_words])
    
    def format_context(self, top_results: list) -> str:
        try:
            formatted_results = ""
            for i, result in enumerate(top_results):
                title = result['title'].strip()
                content = self.trim_content(result['content'], max_words=150)
                formatted_results += f"{i+1}. Title: {title}\nContent: {content}\n\n"
            return formatted_results
        except Exception as e:
            raise e
    
    def get_top_k_contents(self, results: list, k: int = 3) -> list:
        try:
            top_results = sorted(results, key=lambda x: x["score"], reverse=True)[:k]
            return top_results
        except Exception as e:
            raise e