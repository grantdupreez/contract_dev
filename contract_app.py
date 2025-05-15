import streamlit as st
import pandas as pd
import os
import base64
import anthropic
import re
import tempfile
from PyPDF2 import PdfReader
import docx
from datetime import datetime
import hmac
import matplotlib.pyplot as plt
import numpy as np
import altair as alt
import json

def check_password():
    """Returns `True` if the user had a correct password."""
    def login_form():
        with st.form("Credentials"):
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            st.form_submit_button("Log in", on_click=password_entered)

    def password_entered():
        if (st.session_state["username"] in st.secrets["passwords"] and 
            hmac.compare_digest(
                st.session_state["password"],
                st.secrets.passwords[st.session_state["username"]],
            )):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    login_form()
    if "password_correct" in st.session_state:
        st.error("😕 User not known or password incorrect")
    return False

if not check_password():
    st.stop()

# Set page configuration
st.set_page_config(
    page_title="ERP Contract Comparison Tool",
    page_icon="📑",
    layout="wide"
)

# CSS for better styling with enhanced color coding and visualization
st.markdown("""
<style>
    .main { padding: 2rem; }
    .title { font-size: 2.5rem; font-weight: bold; margin-bottom: 1rem; }
    .subtitle { font-size: 1.5rem; margin-bottom: 2rem; }
    .section-header { font-size: 1.8rem; font-weight: bold; margin: 1.5rem 0 1rem 0; 
                    padding-bottom: 0.5rem; border-bottom: 2px solid #f0f2f6; }
    .info-box { background-color: #f8f9fa; padding: 1rem; border-radius: 5px; margin-bottom: 1rem; }
    .highlight { background-color: #ffffcc; padding: 2px; }
    .suggestion { background-color: #e6f7ff; padding: 1rem; border-radius: 5px; 
                margin: 1rem 0; border-left: 4px solid #1890ff; }
    .risk { background-color: #fff2f0; padding: 1rem; border-radius: 5px; 
          margin: 1rem 0; border-left: 4px solid #ff4d4f; }
    .opportunity { background-color: #f6ffed; padding: 1rem; border-radius: 5px; 
                 margin: 1rem 0; border-left: 4px solid #52c41a; }
    
    /* Risk level indicators */
    .risk-high { background-color: #ffcdd2; color: #c62828; padding: 0.2rem 0.5rem; border-radius: 3px; font-weight: bold; }
    .risk-medium { background-color: #fff9c4; color: #f57f17; padding: 0.2rem 0.5rem; border-radius: 3px; font-weight: bold; }
    .risk-low { background-color: #dcedc8; color: #33691e; padding: 0.2rem 0.5rem; border-radius: 3px; font-weight: bold; }
    .risk-favorable { background-color: #bbdefb; color: #0d47a1; padding: 0.2rem 0.5rem; border-radius: 3px; font-weight: bold; }
    
    /* Text diff highlighting */
    .diff-added { background-color: #e6ffed; text-decoration: none; padding: 0.1rem 0.2rem; }
    .diff-removed { background-color: #ffeef0; text-decoration: line-through; padding: 0.1rem 0.2rem; }
    .diff-common { }
    
    /* Enhanced comparison table */
    .comparison-table { 
        width: 100%; 
        border-collapse: collapse; 
        margin: 1rem 0; 
        border: 1px solid #e0e0e0;
        font-size: 0.95rem;
    }
    .comparison-table th { 
        background-color: #f0f2f6; 
        text-align: left; 
        padding: 0.75rem; 
        border: 1px solid #e0e0e0;
        font-weight: bold;
    }
    .comparison-table td { 
        padding: 0.75rem; 
        border: 1px solid #e0e0e0; 
        vertical-align: top;
    }
    .comparison-table tr:nth-child(even) {
        background-color: #f9f9f9;
    }
    .comparison-table .category-header {
        background-color: #e6f0ff;
        font-weight: bold;
    }
    
    /* Side by side comparison styling */
    .side-by-side {
        display: flex;
        margin-bottom: 1rem;
    }
    .side-by-side .contract-col {
        flex: 1;
        padding: 1rem;
        border: 1px solid #e0e0e0;
        border-radius: 5px;
        margin: 0 0.5rem;
    }
    .side-by-side h3 {
        margin-top: 0;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #e0e0e0;
    }
    .category-title {
        font-weight: bold;
        font-size: 1.2rem;
        margin: 1rem 0 0.5rem 0;
        padding-bottom: 0.25rem;
        border-bottom: 1px solid #eaeaea;
        color: #2c3e50;
    }
    
    /* List styling */
    ul.comparison-list {
        padding-left: 1.5rem;
        margin-bottom: 1rem;
    }
    ul.comparison-list li {
        margin-bottom: 0.5rem;
        position: relative;
    }
    ul.comparison-list li:before {
        content: "•";
        position: absolute;
        left: -1rem;
        color: #1890ff;
    }
    
    /* Executive summary styling */
    .exec-summary {
        background-color: #f5f7fa;
        border-radius: 8px;
        padding: 1.5rem;
        margin-bottom: 2rem;
        border-left: 5px solid #1890ff;
    }
    .exec-summary h3 {
        margin-top: 0;
        color: #1f3a60;
    }
    .exec-summary .key-points {
        margin-top: 0.75rem;
    }
    .score-pill {
        display: inline-block;
        padding: 0.35rem 0.65rem;
        border-radius: 1rem;
        font-weight: bold;
        color: white;
        background-color: #4caf50;
        margin-right: 0.5rem;
        font-size: 0.9rem;
    }
    .score-a { background-color: #388e3c; }
    .score-b { background-color: #689f38; }
    .score-c { background-color: #afb42b; }
    .score-d { background-color: #ffa000; }
    .score-f { background-color: #e64a19; }
    
    /* Toggle and collapsible sections */
    .toggle-header {
        cursor: pointer;
        padding: 0.75rem;
        background-color: #f5f5f5;
        border-radius: 4px;
        margin: 0.5rem 0;
        font-weight: bold;
    }
    .toggle-header:hover {
        background-color: #e0e0e0;
    }
    .toggle-content {
        padding: 0.75rem;
        border: 1px solid #e0e0e0;
        border-radius: 0 0 4px 4px;
        margin-bottom: 0.75rem;
    }
    
    /* Key findings in summary */
    .key-finding {
        font-weight: bold;
        color: #1890ff;
    }
    .alert-warning {
        color: #d63031;
        font-weight: bold;
    }
    
    /* Score card */
    .score-card {
        background-color: white;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        padding: 1rem;
        margin-bottom: 1rem;
    }
    .score-card-header {
        font-size: 1.1rem;
        font-weight: bold;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #eaeaea;
        margin-bottom: 0.75rem;
    }
    .score-card-metrics {
        display: flex;
        flex-wrap: wrap;
    }
    .score-metric {
        flex: 1 0 30%;
        margin: 0.35rem;
        text-align: center;
    }
    .score-metric-value {
        font-size: 1.5rem;
        font-weight: bold;
    }
    .score-metric-label {
        font-size: 0.8rem;
        color: #666;
    }
</style>
""", unsafe_allow_html=True)

# Extract text functions
def extract_text(file):
    """Extract text from various file formats."""
    file_extension = os.path.splitext(file.name)[1].lower()
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp:
        temp.write(file.getvalue())
        temp_path = temp.name
    
    try:
        if file_extension == ".pdf":
            pdf_reader = PdfReader(temp_path)
            return "\n".join(page.extract_text() for page in pdf_reader.pages)
        elif file_extension == ".docx":
            doc = docx.Document(temp_path)
            return "\n".join(para.text for para in doc.paragraphs)
        elif file_extension == ".txt":
            with open(temp_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            return "Unsupported file format. Please upload PDF, DOCX, or TXT files."
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

def format_comparison_table_with_risk(text, risk_analysis):
    """
    Format the comparison text into an HTML table structure with risk assessment
    """
    # Split the text into sections based on category headers
    sections = re.split(r'### (.*?)(?:\n|$)', text)
    
    if len(sections) <= 1:
        # If no clear sections, just return formatted text
        return f"<div class='comparison-text'>{text}</div>"
    
    html_output = "<table class='comparison-table'>"
    
    # Process each section
    for i in range(1, len(sections), 2):
        if i < len(sections):
            category = sections[i].strip()
            content = sections[i+1] if i+1 < len(sections) else ""
            
            # Get risk assessment for this category if available
            category_risk = None
            if risk_analysis and 'categories' in risk_analysis:
                for cat in risk_analysis['categories']:
                    if isinstance(cat, dict) and 'name' in cat:
                        if cat['name'].lower() == category.lower():
                            category_risk = cat
                            break
            
            # Split content into contract1 and contract2 parts
            parts = re.split(r'#### (Contract 1|Contract 2)(?:\n|$)', content)
            
            if len(parts) > 2:  # We have proper split between contracts
                # Add risk indicators if available
                risk_indicators = ""
                if category_risk:
                    try:
                        risk_c1 = category_risk.get('contract1_risk', 'medium')
                        risk_c2 = category_risk.get('contract2_risk', 'medium')
                        
                        # Ensure risk levels are valid strings
                        if not isinstance(risk_c1, str):
                            risk_c1 = 'medium'
                        if not isinstance(risk_c2, str):
                            risk_c2 = 'medium'
                        
                        # Normalize risk levels to lower case
                        risk_c1 = risk_c1.lower()
                        risk_c2 = risk_c2.lower()
                        
                        # Validate risk levels
                        valid_risks = ['high', 'medium', 'low', 'favorable']
                        risk_c1 = risk_c1 if risk_c1 in valid_risks else 'medium'
                        risk_c2 = risk_c2 if risk_c2 in valid_risks else 'medium'
                        
                        risk_c1_html = f"<span class='risk-{risk_c1}'>{risk_c1.upper()}</span>"
                        risk_c2_html = f"<span class='risk-{risk_c2}'>{risk_c2.upper()}</span>"
                        
                        html_output += f"<tr class='category-header'><th colspan='2'>{category}</th></tr>"
                        html_output += f"<tr><th>Contract 1 {risk_c1_html}</th><th>Contract 2 {risk_c2_html}</th></tr>"
                    except Exception as e:
                        # Fall back to simple header without risk indicators
                        html_output += f"<tr class='category-header'><th colspan='2'>{category}</th></tr>"
                        html_output += "<tr><th>Contract 1</th><th>Contract 2</th></tr>"
                else:
                    html_output += f"<tr class='category-header'><th colspan='2'>{category}</th></tr>"
                    html_output += "<tr><th>Contract 1</th><th>Contract 2</th></tr>"
                
                # Find the content for each contract
                contract1_content = ""
                contract2_content = ""
                
                for j in range(1, len(parts), 2):
                    if j < len(parts):
                        contract_type = parts[j].strip()
                        contract_content = parts[j+1] if j+1 < len(parts) else ""
                        
                        # Remove any lines that only contain "#" symbol
                        contract_content = re.sub(r'(?:^|\n)#\s*(?:$|\n)', '\n', contract_content)
                        
                        # Process risk tags if they exist in the content
                        if category_risk:
                            try:
                                # Look for any specific clauses with risk tags
                                if contract_type == "Contract 1" and 'contract1_clauses' in category_risk:
                                    clauses = category_risk['contract1_clauses']
                                    if isinstance(clauses, list):
                                        for clause in clauses:
                                            if isinstance(clause, dict) and 'text' in clause and 'risk' in clause:
                                                clause_text = clause['text']
                                                risk_level = clause['risk']
                                                
                                                # Validate risk level
                                                if not isinstance(risk_level, str):
                                                    risk_level = 'medium'
                                                risk_level = risk_level.lower()
                                                risk_level = risk_level if risk_level in valid_risks else 'medium'
                                                
                                                # Replace the clause text with a risk-highlighted version
                                                contract_content = contract_content.replace(
                                                    f"- {clause_text}", 
                                                    f"- <span class='risk-{risk_level}'>{clause_text}</span>"
                                                )
                                elif contract_type == "Contract 2" and 'contract2_clauses' in category_risk:
                                    clauses = category_risk['contract2_clauses']
                                    if isinstance(clauses, list):
                                        for clause in clauses:
                                            if isinstance(clause, dict) and 'text' in clause and 'risk' in clause:
                                                clause_text = clause['text']
                                                risk_level = clause['risk']
                                                
                                                # Validate risk level
                                                if not isinstance(risk_level, str):
                                                    risk_level = 'medium'
                                                risk_level = risk_level.lower()
                                                risk_level = risk_level if risk_level in valid_risks else 'medium'
                                                
                                                # Replace the clause text with a risk-highlighted version
                                                contract_content = contract_content.replace(
                                                    f"- {clause_text}", 
                                                    f"- <span class='risk-{risk_level}'>{clause_text}</span>"
                                                )
                            except Exception as e:
                                # If there's an error processing risk tags, just continue without them
                                pass
                        
                        # Convert bullet points to HTML lists
                        contract_content = re.sub(r'(?:^|\n)- (.*?)(?:$|\n)', 
                                                r'\n<li>\1</li>', contract_content)
                        contract_content = f"<ul class='comparison-list'>{contract_content}</ul>"
                        
                        if "Contract 1" in contract_type:
                            contract1_content = contract_content
                        elif "Contract 2" in contract_type:
                            contract2_content = contract_content
                
                html_output += f"<tr><td>{contract1_content}</td><td>{contract2_content}</td></tr>"
            else:
                # If no clear split between contracts, just show the content as is
                
                # Remove any lines that only contain "#" symbol
                content = re.sub(r'(?:^|\n)#\s*(?:$|\n)', '\n', content)
                
                content = re.sub(r'(?:^|\n)- (.*?)(?:$|\n)', r'\n<li>\1</li>', content)
                content = f"<ul class='comparison-list'>{content}</ul>"
                html_output += f"<tr class='category-header'><th colspan='2'>{category}</th></tr>"
                html_output += f"<tr><td colspan='2'>{content}</td></tr>"
    
    html_output += "</table>"
    return html_output

def create_executive_summary(analysis_result, risk_analysis, contract1_name, contract2_name):
    """Generate an executive summary from the analysis results and risk assessment."""
    
    if not risk_analysis:
        return "<div class='exec-summary'><h3>Executive Summary</h3><p>Risk analysis data not available. Please rerun the comparison.</p></div>"
    
    # Get overall scores and ensure they are integers
    try:
        c1_score = int(risk_analysis.get('contract1_overall_score', 70))
    except (ValueError, TypeError):
        c1_score = 70
        
    try:
        c2_score = int(risk_analysis.get('contract2_overall_score', 70))
    except (ValueError, TypeError):
        c2_score = 70
    
    # Determine letter grades
    def get_letter_grade(score):
        try:
            score_num = int(score)
            if score_num >= 90: return "A"
            elif score_num >= 80: return "B"
            elif score_num >= 70: return "C"
            elif score_num >= 60: return "D"
            else: return "F"
        except (ValueError, TypeError):
            # Default to C if score cannot be converted to int
            return "C"
    
    c1_grade = get_letter_grade(c1_score)
    c2_grade = get_letter_grade(c2_score)
    
    # Get key advantages and disadvantages
    c1_advantages = risk_analysis.get('contract1_advantages', ['No specific advantages identified'])
    c1_disadvantages = risk_analysis.get('contract1_disadvantages', ['No specific disadvantages identified'])
    c2_advantages = risk_analysis.get('contract2_advantages', ['No specific advantages identified'])
    c2_disadvantages = risk_analysis.get('contract2_disadvantages', ['No specific disadvantages identified'])
    
    # Ensure lists are not empty and are actual lists
    if not c1_advantages or not isinstance(c1_advantages, list):
        c1_advantages = ['No specific advantages identified']
    if not c1_disadvantages or not isinstance(c1_disadvantages, list):
        c1_disadvantages = ['No specific disadvantages identified']
    if not c2_advantages or not isinstance(c2_advantages, list):
        c2_advantages = ['No specific advantages identified']
    if not c2_disadvantages or not isinstance(c2_disadvantages, list):
        c2_disadvantages = ['No specific disadvantages identified']
    
    # Get recommendations
    recommendation = risk_analysis.get('recommendation', 'Further detailed analysis recommended.')
    if not recommendation or not isinstance(recommendation, str):
        recommendation = 'Further detailed analysis recommended.'
    
    # Create the summary HTML
    html = f"""
    <div class="exec-summary">
        <h3>Executive Summary: Contract Comparison</h3>
        <div class="side-by-side">
            <div class="contract-col">
                <h4>{contract1_name}</h4>
                <p><span class="score-pill score-{c1_grade.lower()}">{c1_grade}</span> Overall Score: {c1_score}/100</p>
                <h5>Key Advantages</h5>
                <ul>
    """
    
    for adv in c1_advantages[:3]:  # Limit to top 3
        html += f"<li>{adv}</li>"
    
    html += """
                </ul>
                <h5>Key Concerns</h5>
                <ul>
    """
    
    for disadv in c1_disadvantages[:3]:  # Limit to top 3
        html += f"<li>{disadv}</li>"
    
    html += f"""
                </ul>
            </div>
            <div class="contract-col">
                <h4>{contract2_name}</h4>
                <p><span class="score-pill score-{c2_grade.lower()}">{c2_grade}</span> Overall Score: {c2_score}/100</p>
                <h5>Key Advantages</h5>
                <ul>
    """
    
    for adv in c2_advantages[:3]:  # Limit to top 3
        html += f"<li>{adv}</li>"
    
    html += """
                </ul>
                <h5>Key Concerns</h5>
                <ul>
    """
    
    for disadv in c2_disadvantages[:3]:  # Limit to top 3
        html += f"<li>{disadv}</li>"
    
    html += f"""
                </ul>
            </div>
        </div>
        <h5>Recommendation</h5>
        <div class="key-points">
            <p>{recommendation}</p>
        </div>
    </div>
    """
    
    return html

def create_score_card(risk_analysis, contract1_name, contract2_name):
    """Generate a score card visualization from the risk analysis."""
    
    # Get scores for different dimensions
    c1_dimensions = risk_analysis.get('contract1_dimension_scores', {})
    c2_dimensions = risk_analysis.get('contract2_dimension_scores', {})
    
    # Create default dimensions if missing
    if not c1_dimensions:
        c1_dimensions = {
            "Pricing": 70,
            "Risk Allocation": 70,
            "Service Levels": 70,
            "Flexibility": 70,
            "Legal Protection": 70
        }
    if not c2_dimensions:
        c2_dimensions = {
            "Pricing": 70,
            "Risk Allocation": 70,
            "Service Levels": 70,
            "Flexibility": 70,
            "Legal Protection": 70
        }
    
    # Prepare data for the chart
    categories = []
    c1_scores = []
    c2_scores = []
    
    # Ensure both dimension sets have the same categories
    all_categories = set(list(c1_dimensions.keys()) + list(c2_dimensions.keys()))
    
    for cat in all_categories:
        categories.append(cat)
        c1_scores.append(c1_dimensions.get(cat, 70))  # Default to 70 if missing
        c2_scores.append(c2_dimensions.get(cat, 70))  # Default to 70 if missing
    
    # Create chart data
    chart_data = pd.DataFrame({
        'Category': categories + categories,
        'Score': c1_scores + c2_scores,
        'Contract': [contract1_name] * len(categories) + [contract2_name] * len(categories)
    })
    
    # Create the chart
    try:
        chart = alt.Chart(chart_data).mark_bar().encode(
            x=alt.X('Category:N', title=None),
            y=alt.Y('Score:Q', scale=alt.Scale(domain=[0, 100])),
            color=alt.Color('Contract:N', scale=alt.Scale(
                domain=[contract1_name, contract2_name],
                range=['#1890ff', '#52c41a']
            )),
            tooltip=['Category', 'Score', 'Contract']
        ).properties(
            title='Comparison by Category',
            width=600,
            height=300
        )
        return chart
    except Exception as e:
        st.warning(f"Could not create chart: {str(e)}")
        # Return a placeholder message
        return "Chart generation failed. Please check the data format."

def compare_contracts_with_claude(contract1_text, contract2_text, analysis_focus, custom_prompt):
    """Use Claude AI to compare contracts and generate insights with risk assessment."""
    
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    
    # Build context based on selected focus areas and custom instructions
    context = "As a procurement expert specialising in IT services for ERP projects, create a detailed side-by-side comparison of these contracts "
    
    # Add selected focus areas
    if analysis_focus:
        context += "specifically focusing on the following aspects: " + ", ".join(analysis_focus) + ". "
    
    # Add custom instructions
    if custom_prompt:
        context += custom_prompt
    
    # Enhanced prompt with risk assessment
    prompt = f"""
    {context}
    
    CONTRACT 1:
    {contract1_text[:25000]}
    
    CONTRACT 2:
    {contract2_text[:25000]}
    
    Create a structured side-by-side comparison with these requirements:
    
    1. Format the response as a clear side-by-side comparison for each selected topic
    2. For each topic, use this structure:
       ### [Topic Name]
       #### Contract 1
       - Key point 1
       - Key point 2
       
       #### Contract 2
       - Key point 1
       - Key point 2
    
    3. Directly compare equivalent clauses and terms between the contracts
    4. Bold any significant differences or important terms
    5. For each topic, highlight strengths and weaknesses of each contract
    6. If one contract has a provision that the other lacks, explicitly note this
    7. Include specific clause references when possible
    8. Focus ONLY on the selected topics/areas specified in the instructions
    9. Use concise, clear British English focusing on the practical implications
    10. End with a brief section highlighting the most critical differences that would impact decision-making
    
    ADDITIONAL TASK: After completing the comparison, provide a separate structured risk assessment in JSON format enclosed in triple backticks with "json" language specifier.
    """
    
    try:
        response = client.messages.create(
            model=st.secrets["ANTHROPIC_MODEL"],
            max_tokens=6000,
            temperature=0.2,
            system="You are an expert procurement analyst specialising in IT and ERP service contracts. Create a clear side-by-side comparison of contract terms, focused only on the specific topics requested. Format your response as a structured comparison with separate sections for each contract under each topic. Use bullet points and bold formatting for clarity and emphasis on key differences. Write in British English. Additionally, create a risk assessment in JSON format with these fields: contract1_overall_score, contract2_overall_score (both 0-100), dimension_scores for each contract covering Pricing, Risk Allocation, Service Levels, Flexibility, and Legal Protection, categories with risk levels (high/medium/low/favorable) for clauses, and lists of advantages, disadvantages and a recommendation.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Extract the main comparison text and the JSON risk assessment
        full_response = response.content[0].text
        
        # Find and extract the JSON part (assuming it's at the end)
        json_match = re.search(r'```json\s*(.*?)\s*```', full_response, re.DOTALL)
        
        # Create default risk analysis with basic structure
        default_risk_analysis = {
            "contract1_overall_score": 70,
            "contract2_overall_score": 70,
            "contract1_dimension_scores": {
                "Pricing": 70,
                "Risk Allocation": 70,
                "Service Levels": 70,
                "Flexibility": 70,
                "Legal Protection": 70
            },
            "contract2_dimension_scores": {
                "Pricing": 70,
                "Risk Allocation": 70,
                "Service Levels": 70,
                "Flexibility": 70,
                "Legal Protection": 70
            },
            "categories": [],
            "contract1_advantages": ["Good overall terms"],
            "contract1_disadvantages": ["Could be improved in some areas"],
            "contract2_advantages": ["Good overall terms"],
            "contract2_disadvantages": ["Could be improved in some areas"],
            "recommendation": "Both contracts have strengths and weaknesses. Further analysis recommended."
        }
        
        if json_match:
            json_text = json_match.group(1)
            # Remove the JSON part from the main response
            comparison_text = full_response[:json_match.start()].strip()
            
            # Parse the JSON
            try:
                risk_analysis = json.loads(json_text)
                
                # Ensure all required fields exist with defaults if not present
                risk_analysis.setdefault("contract1_overall_score", 70)
                risk_analysis.setdefault("contract2_overall_score", 70)
                
                # Ensure dimension scores exist
                if "contract1_dimension_scores" not in risk_analysis:
                    risk_analysis["contract1_dimension_scores"] = default_risk_analysis["contract1_dimension_scores"]
                if "contract2_dimension_scores" not in risk_analysis:
                    risk_analysis["contract2_dimension_scores"] = default_risk_analysis["contract2_dimension_scores"]
                
                # Ensure other required fields exist
                risk_analysis.setdefault("categories", [])
                risk_analysis.setdefault("contract1_advantages", ["Good overall terms"])
                risk_analysis.setdefault("contract1_disadvantages", ["Could be improved in some areas"])
                risk_analysis.setdefault("contract2_advantages", ["Good overall terms"])
                risk_analysis.setdefault("contract2_disadvantages", ["Could be improved in some areas"])
                risk_analysis.setdefault("recommendation", "Both contracts have strengths and weaknesses. Further analysis recommended.")
                
            except json.JSONDecodeError as e:
                # If JSON parsing fails, use default structure
                st.warning(f"Error parsing risk assessment JSON. Using default values. Error: {str(e)}")
                risk_analysis = default_risk_analysis
                comparison_text = full_response
        else:
            # If no JSON found, use default structure
            st.warning("No risk assessment JSON found in the response. Using default values.")
            comparison_text = full_response
            risk_analysis = default_risk_analysis
            
        return comparison_text, risk_analysis
    except Exception as e:
        st.error(f"Error calling Claude API: {str(e)}")
        # Return a basic response and default risk analysis
        return "Error analyzing contracts. Please try again with different parameters or contact support.", default_risk_analysis

def main():
    # App header
    st.markdown('<div class="title">ERP Contract Comparison Tool</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Enhanced Side-by-Side Comparison with Risk Assessment</div>', unsafe_allow_html=True)
    
    # Initialize session state
    if 'analysis_history' not in st.session_state:
        st.session_state.analysis_history = []
    
    # Sidebar for settings
    with st.sidebar:
        st.markdown("## Analysis Focus (Required)")
        
        analysis_focus = st.multiselect(
            "Select specific areas to compare",
            ["Pricing Structure", "Service Level Agreements", "Implementation Timeline",
             "Scope of Work", "Maintenance & Support", "Data Security", "Exit Strategy",
             "Intellectual Property", "Change Management", "Performance Metrics"]
        )
        
        custom_prompt = st.text_area("Custom Analysis Instructions (optional)", 
                             help="Add specific instructions for the contract comparison")
        
        # Warning if no focus or instruction provided
        if not analysis_focus and not custom_prompt:
            st.warning("⚠️ You must select at least one focus area or provide custom instructions")
        
        st.markdown("## About")
        st.info("""
        This tool creates side-by-side comparisons of ERP service contracts using Claude AI.
        Select specific focus areas to generate a targeted comparison between contracts.
        Results include:
        - Risk assessment with color-coding
        - Overall contract scoring
        - Executive summary with key advantages and concerns
        """)
    
    # Main interface
    tab1, tab2, tab3 = st.tabs(["Contract Upload", "Comparison Results", "History"])
    
    # Contract Upload Tab
    with tab1:
        st.markdown('<div class="section-header">Upload Contracts for Comparison</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Contract 1")
            contract1_file = st.file_uploader("Upload first contract", type=["pdf", "docx", "txt"], key="contract1")
            contract1_name = st.text_input("Contract 1 Name/Reference", placeholder="e.g., Vendor A Proposal")
            
            if contract1_file:
                st.success(f"Successfully uploaded: {contract1_file.name}")
                contract1_text = extract_text(contract1_file)
                st.markdown("#### Preview")
                st.text_area("", contract1_text[:1000] + "...", height=200, disabled=True)
        
        with col2:
            st.markdown("### Contract 2")
            contract2_file = st.file_uploader("Upload second contract", type=["pdf", "docx", "txt"], key="contract2")
            contract2_name = st.text_input("Contract 2 Name/Reference", placeholder="e.g., Vendor B Proposal")
            
            if contract2_file:
                st.success(f"Successfully uploaded: {contract2_file.name}")
                contract2_text = extract_text(contract2_file)
                st.markdown("#### Preview")
                st.text_area("", contract2_text[:1000] + "...", height=200, disabled=True)
        
        # Analyse button
        analyze_col1, analyze_col2, analyze_col3 = st.columns([1, 2, 1])
        with analyze_col2:
            # Button is disabled if no files or no focus areas/custom instructions
            analyze_button = st.button("Compare Contracts", type="primary", use_container_width=True, 
                                      disabled=not (contract1_file and contract2_file and (analysis_focus or custom_prompt)))
        
        if not (analysis_focus or custom_prompt):
            st.error("You must select at least one focus area or provide custom analysis instructions")
        
        if analyze_button and contract1_file and contract2_file and (analysis_focus or custom_prompt):
            with st.spinner("Creating enhanced comparison with risk assessment... This may take a moment..."):
                contract1_text = extract_text(contract1_file)
                contract2_text = extract_text(contract2_file)
                
                # Default names if not provided
                if not contract1_name:
                    contract1_name = contract1_file.name
                if not contract2_name:
                    contract2_name = contract2_file.name
                
                # Generate the enhanced comparison with risk assessment
                analysis_result, risk_analysis = compare_contracts_with_claude(
                    contract1_text, 
                    contract2_text, 
                    analysis_focus, 
                    custom_prompt
                )
                
                # Add to history
                analysis_entry = {
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'contract1_name': contract1_name,
                    'contract2_name': contract2_name,
                    'focus_areas': analysis_focus,
                    'custom_prompt': custom_prompt,
                    'result': analysis_result,
                    'risk_analysis': risk_analysis
                }
                st.session_state.analysis_history.append(analysis_entry)
                st.session_state.current_analysis = analysis_entry
                
                # Switch to results tab
                st.query_params["tab"] = "results"
                st.rerun()
                
    # Comparison Results Tab
    with tab2:
        if 'current_analysis' in st.session_state:
            analysis = st.session_state.current_analysis
            
            st.markdown(f'<div class="section-header">Enhanced Contract Comparison</div>', unsafe_allow_html=True)
            
            # Show executive summary if risk analysis is available
            if 'risk_analysis' in analysis and analysis['risk_analysis']:
                exec_summary = create_executive_summary(
                    analysis['result'], 
                    analysis['risk_analysis'], 
                    analysis['contract1_name'], 
                    analysis['contract2_name']
                )
                st.markdown(exec_summary, unsafe_allow_html=True)
                
                # Create and display score card visualization
                score_chart = create_score_card(
                    analysis['risk_analysis'], 
                    analysis['contract1_name'], 
                    analysis['contract2_name']
                )
                st.altair_chart(score_chart, use_container_width=True)
            
            # Display comparison metadata
            metadata_col1, metadata_col2 = st.columns(2)
            with metadata_col1:
                st.markdown(f"**Contracts:** {analysis['contract1_name']} vs {analysis['contract2_name']}")
                st.markdown(f"**Analysis performed:** {analysis['timestamp']}")
            
            with metadata_col2:
                focus_areas = "All selected: " + ", ".join(analysis['focus_areas']) if analysis['focus_areas'] else "None"
                st.markdown(f"**Focus Areas:** {focus_areas}")
                if analysis['custom_prompt']:
                    st.markdown(f"**Custom Instructions:** {analysis['custom_prompt']}")
            
            # Toggle for viewing all content vs. just differences
            view_mode = st.radio("View Mode:", ("Complete Comparison", "Risk Assessment Only"), horizontal=True)
            
            if view_mode == "Complete Comparison":
                # Process and display the comparison in a table format with risk assessment
                formatted_comparison = format_comparison_table_with_risk(
                    analysis['result'], 
                    analysis.get('risk_analysis')
                )
                st.markdown(formatted_comparison, unsafe_allow_html=True)
            else:
                # Show only the risk assessment aspects
                st.markdown("## Risk Assessment Details")
                
                if 'risk_analysis' in analysis and analysis['risk_analysis']:
                    risk_data = analysis['risk_analysis']
                    
                    # Display risk analysis for each category
                    for category in risk_data.get('categories', []):
                        with st.expander(f"{category['name']} - Contract 1: {category['contract1_risk'].upper()}, Contract 2: {category['contract2_risk'].upper()}"):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.markdown(f"### {analysis['contract1_name']}")
                                st.markdown(f"**Risk Level:** {category['contract1_risk'].upper()}")
                                
                                if 'contract1_clauses' in category:
                                    st.markdown("#### Key Risk Points:")
                                    for clause in category['contract1_clauses']:
                                        risk_color = {
                                            'high': 'red',
                                            'medium': 'orange',
                                            'low': 'green',
                                            'favorable': 'blue'
                                        }.get(clause['risk'].lower(), 'grey')
                                        
                                        st.markdown(f"- <span style='color:{risk_color};font-weight:bold;'>[{clause['risk'].upper()}]</span> {clause['text']}", unsafe_allow_html=True)
                            
                            with col2:
                                st.markdown(f"### {analysis['contract2_name']}")
                                st.markdown(f"**Risk Level:** {category['contract2_risk'].upper()}")
                                
                                if 'contract2_clauses' in category:
                                    st.markdown("#### Key Risk Points:")
                                    for clause in category['contract2_clauses']:
                                        risk_color = {
                                            'high': 'red',
                                            'medium': 'orange',
                                            'low': 'green',
                                            'favorable': 'blue'
                                        }.get(clause['risk'].lower(), 'grey')
                                        
                                        st.markdown(f"- <span style='color:{risk_color};font-weight:bold;'>[{clause['risk'].upper()}]</span> {clause['text']}", unsafe_allow_html=True)
                else:
                    st.error("No risk assessment data available for this comparison.")
            
            # Download buttons for the comparison and risk assessment
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="Download Full Comparison Report",
                    data=f"# Side-by-Side Contract Comparison: {analysis['contract1_name']} vs {analysis['contract2_name']}\n\n" +
                         f"Analysis Date: {analysis['timestamp']}\n\n" +
                         f"Focus Areas: {', '.join(analysis['focus_areas']) if analysis['focus_areas'] else 'Custom analysis'}\n\n" +
                         analysis['result'],
                    file_name=f"contract_comparison_{datetime.now().strftime('%Y%m%d')}.md",
                    mime="text/markdown"
                )
            
            with col2:
                if 'risk_analysis' in analysis and analysis['risk_analysis']:
                    st.download_button(
                        label="Download Risk Assessment (JSON)",
                        data=json.dumps(analysis['risk_analysis'], indent=2),
                        file_name=f"risk_assessment_{datetime.now().strftime('%Y%m%d')}.json",
                        mime="application/json"
                    )
        else:
            st.info("Upload contracts and select focus areas to generate a side-by-side comparison with risk assessment")
            
    # History Tab
    with tab3:
        st.markdown('<div class="section-header">Comparison History</div>', unsafe_allow_html=True)
        
        if st.session_state.analysis_history:
            for i, analysis in enumerate(reversed(st.session_state.analysis_history)):
                with st.expander(f"{analysis['contract1_name']} vs {analysis['contract2_name']} - {analysis['timestamp']}"):
                    # Show focus areas
                    focus_areas = "Areas: " + ", ".join(analysis['focus_areas']) if analysis['focus_areas'] else "Custom analysis"
                    st.markdown(f"**{focus_areas}**")
                    
                    # Show scores if available
                    if 'risk_analysis' in analysis and analysis['risk_analysis']:
                        c1_score = analysis['risk_analysis'].get('contract1_overall_score', 'N/A')
                        c2_score = analysis['risk_analysis'].get('contract2_overall_score', 'N/A')
                        st.markdown(f"**Scores:** {analysis['contract1_name']}: {c1_score}/100, {analysis['contract2_name']}: {c2_score}/100")
                    
                    # Show a preview of the analysis
                    preview_length = min(500, len(analysis['result']))
                    st.markdown(analysis['result'][:preview_length] + "..." if len(analysis['result']) > preview_length else analysis['result'])
                    
                    # Button to view this comparison
                    if st.button(f"View Full Comparison", key=f"view_{i}"):
                        st.session_state.current_analysis = analysis
                        st.query_params["tab"] = "results"
                        st.rerun()
        else:
            st.info("Your comparison history will appear here")

if __name__ == "__main__":
    main()
