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
    
    /* Risk level indicators - Light mode */
    .risk-high { background-color: #ffcdd2; color: #c62828; padding: 0.2rem 0.5rem; border-radius: 3px; font-weight: bold; }
    .risk-medium { background-color: #fff9c4; color: #f57f17; padding: 0.2rem 0.5rem; border-radius: 3px; font-weight: bold; }
    .risk-low { background-color: #dcedc8; color: #33691e; padding: 0.2rem 0.5rem; border-radius: 3px; font-weight: bold; }
    .risk-favorable { background-color: #bbdefb; color: #0d47a1; padding: 0.2rem 0.5rem; border-radius: 3px; font-weight: bold; }
    
    /* Executive summary styling - Light mode */
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
    
    /* DARK MODE STYLES */
    @media (prefers-color-scheme: dark) {
        /* General dark mode adjustments */
        .section-header { 
            border-bottom: 2px solid #30363d; 
        }
        
        /* Risk level indicators - Dark mode */
        .risk-high { 
            background-color: rgba(220, 38, 38, 0.2); 
            color: #ef4444; 
        }
        .risk-medium { 
            background-color: rgba(245, 158, 11, 0.2); 
            color: #f59e0b; 
        }
        .risk-low { 
            background-color: rgba(16, 185, 129, 0.2); 
            color: #10b981; 
        }
        .risk-favorable { 
            background-color: rgba(59, 130, 246, 0.2); 
            color: #3b82f6; 
        }
        
        /* Executive summary styling - Dark mode */
        .exec-summary {
            background-color: #1f2937;
            border-left: 5px solid #3b82f6;
        }
        .exec-summary h3 {
            color: #e5e7eb;
        }
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

def highlight_differences(text1, text2):
    """
    Highlight differences between two text strings
    Returns HTML-formatted text with differences highlighted
    """
    # Simple word-by-word diff highlighting
    words1 = text1.split()
    words2 = text2.split()
    
    result1 = []
    result2 = []
    
    # Very simple diff algorithm
    i, j = 0, 0
    while i < len(words1) and j < len(words2):
        if words1[i] == words2[j]:
            result1.append(f'<span class="diff-common">{words1[i]}</span>')
            result2.append(f'<span class="diff-common">{words2[j]}</span>')
            i += 1
            j += 1
        elif i+1 < len(words1) and words1[i+1] == words2[j]:
            # Word removed in text2
            result1.append(f'<span class="diff-removed">{words1[i]}</span>')
            i += 1
        elif j+1 < len(words2) and words1[i] == words2[j+1]:
            # Word added in text2
            result2.append(f'<span class="diff-added">{words2[j]}</span>')
            j += 1
        else:
            # Changed word
            result1.append(f'<span class="diff-changed">{words1[i]}</span>')
            result2.append(f'<span class="diff-changed">{words2[j]}</span>')
            i += 1
            j += 1
    
    # Add remaining words
    while i < len(words1):
        result1.append(f'<span class="diff-removed">{words1[i]}</span>')
        i += 1
    
    while j < len(words2):
        result2.append(f'<span class="diff-added">{words2[j]}</span>')
        j += 1
    
    return ' '.join(result1), ' '.join(result2)

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
    
    3. Directly compare equivalent clauses and terms between the contracts - make sure each bullet point in Contract 1 has a corresponding bullet point in Contract 2 if possible
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
    st.markdown('<div class="subtitle">Enhanced Side-by-Side Comparison with Interactive Features</div>', unsafe_allow_html=True)
    
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
        This tool creates interactive side-by-side comparisons of ERP service contracts.
        
        Features include:
        - Text difference highlighting between contracts
        - Collapsible sections for easier navigation
        - Interactive toggles to focus on differences
        - Risk assessment with color-coding
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
            with st.spinner("Creating enhanced comparison with interactive features... This may take a moment..."):
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
            
            # Process and display the enhanced comparison with interactive features
            st.markdown("### Interactive Comparison")
            
            # Native Streamlit controls instead of JavaScript
            col1, col2 = st.columns([1, 1])
            with col1:
                diff_view = st.selectbox(
                    "View Mode:", 
                    ["Show All Content", "Show Differences Only"],
                    key="diff_view"
                )
            with col2:
                st.write("&nbsp;")  # Spacer
                sections_expanded = st.checkbox("Expand All Sections", value=True, key="expand_sections")
            
            # Process the comparison text into sections for Streamlit expanders
            sections = re.split(r'### (.*?)(?:\n|$)', analysis['result'])
            
            if len(sections) > 1:
                # For each section, create a Streamlit expander
                for i in range(1, len(sections), 2):
                    if i < len(sections):
                        category = sections[i].strip()
                        content = sections[i+1] if i+1 < len(sections) else ""
                        
                        # Get risk assessment for this category if available
                        category_risk = None
                        risk_level_html = ""
                        if 'risk_analysis' in analysis and analysis['risk_analysis'] and 'categories' in analysis['risk_analysis']:
                            for cat in analysis['risk_analysis']['categories']:
                                if isinstance(cat, dict) and 'name' in cat:
                                    if cat['name'].lower() == category.lower():
                                        category_risk = cat
                                        # Add risk indicators if available
                                        try:
                                            risk_c1 = cat.get('contract1_risk', 'medium').upper()
                                            risk_c2 = cat.get('contract2_risk', 'medium').upper()
                                            risk_level_html = f" - C1: {risk_c1}, C2: {risk_c2}"
                                        except:
                                            pass
                                        break

                        # Create a Streamlit expander for each section
                        with st.expander(f"{category}{risk_level_html}", expanded=sections_expanded):
                            # Split content into contract1 and contract2 parts
                            parts = re.split(r'#### (Contract 1|Contract 2)(?:\n|$)', content)
                            
                            if len(parts) > 2:  # We have proper split between contracts
                                # Side-by-side columns for contract comparison
                                col1, col2 = st.columns(2)
                                
                                for j in range(1, len(parts), 2):
                                    if j < len(parts):
                                        contract_type = parts[j].strip()
                                        contract_content = parts[j+1] if j+1 < len(parts) else ""
                                        
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
                                                                
                                                                # Add risk highlight using Streamlit markdown
                                                                contract_content = contract_content.replace(
                                                                    f"- {clause_text}", 
                                                                    f"- **[{risk_level.upper()}]** {clause_text}"
                                                                )
                                                elif contract_type == "Contract 2" and 'contract2_clauses' in category_risk:
                                                    clauses = category_risk['contract2_clauses']
                                                    if isinstance(clauses, list):
                                                        for clause in clauses:
                                                            if isinstance(clause, dict) and 'text' in clause and 'risk' in clause:
                                                                clause_text = clause['text']
                                                                risk_level = clause['risk']
                                                                
                                                                # Add risk highlight using Streamlit markdown
                                                                contract_content = contract_content.replace(
                                                                    f"- {clause_text}", 
                                                                    f"- **[{risk_level.upper()}]** {clause_text}"
                                                                )
                                            except Exception as e:
                                                # If there's an error processing risk tags, just continue without them
                                                pass
                                        
                                        # Display contract in the appropriate column
                                        # Using smaller heading with custom styling to eliminate extra spacing
                                        if contract_type == "Contract 1":
                                            with col1:
                                                st.markdown(f"<h5 style='margin-top:0'>{analysis['contract1_name']}</h5>", unsafe_allow_html=True)
                                                st.markdown(contract_content)
                                        elif contract_type == "Contract 2":
                                            with col2:
                                                st.markdown(f"<h5 style='margin-top:0'>{analysis['contract2_name']}</h5>", unsafe_allow_html=True)
                                                st.markdown(contract_content)
                            else:
                                # If no clear split between contracts, just show the content as is
                                st.markdown(content)
                        
                        # Add a visual diff comparison section if selected
                        if diff_view == "Show Differences Only":
                            with st.expander("🔍 View Text Differences", expanded=True):
                                # Extract bullet points from both contracts
                                parts = re.split(r'#### (Contract 1|Contract 2)(?:\n|$)', content)
                                
                                contract1_content = ""
                                contract2_content = ""
                                
                                for j in range(1, len(parts), 2):
                                    if j < len(parts):
                                        contract_type = parts[j].strip()
                                        if contract_type == "Contract 1":
                                            contract1_content = parts[j+1] if j+1 < len(parts) else ""
                                        elif contract_type == "Contract 2":
                                            contract2_content = parts[j+1] if j+1 < len(parts) else ""
                                
                                # Extract bullet points
                                bullet_pattern = r'(?:^|\n)- (.*?)(?:$|\n)'
                                bullets1 = re.findall(bullet_pattern, contract1_content)
                                bullets2 = re.findall(bullet_pattern, contract2_content)
                                
                                # Display differences
                                diff_col1, diff_col2 = st.columns(2)
                                
                                with diff_col1:
                                    st.markdown(f"#### Unique to {analysis['contract1_name']}")
                                    unique_to_1 = [b for b in bullets1 if b not in bullets2]
                                    if unique_to_1:
                                        for bullet in unique_to_1:
                                            st.markdown(f"- 🔴 {bullet}")
                                    else:
                                        st.markdown("*No unique points*")
                                        
                                with diff_col2:
                                    st.markdown(f"#### Unique to {analysis['contract2_name']}")
                                    unique_to_2 = [b for b in bullets2 if b not in bullets1]
                                    if unique_to_2:
                                        for bullet in unique_to_2:
                                            st.markdown(f"- 🟢 {bullet}")
                                    else:
                                        st.markdown("*No unique points*")
            else:
                # If no section found, display the raw text
                st.markdown(analysis['result'])
            
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
            st.info("Upload contracts and select focus areas to generate an interactive side-by-side comparison")
            
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
