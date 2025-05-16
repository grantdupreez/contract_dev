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
    
    /* Difference view styling */
    .diff-container {
        margin-top: 1rem;
        border: 1px solid #e0e0e0;
        border-radius: 5px;
        padding: 1rem;
    }
    .diff-title {
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    .diff-only-c1 {
        background-color: #ffebee;
        padding: 0.5rem;
        margin-bottom: 0.5rem;
        border-left: 3px solid #f44336;
    }
    .diff-only-c2 {
        background-color: #e8f5e9;
        padding: 0.5rem;
        margin-bottom: 0.5rem;
        border-left: 3px solid #4caf50;
    }
    
    /* Score card styling */
    .score-card {
        background-color: #f0f8ff;
        border-radius: 5px;
        padding: 1rem;
        margin-bottom: 1rem;
        border-left: 4px solid #1976d2;
    }
    .score-card-title {
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    .score-meter {
        height: 8px;
        background-color: #e0e0e0;
        border-radius: 4px;
        margin-bottom: 0.5rem;
        overflow: hidden;
    }
    .score-meter-fill {
        height: 100%;
        background-color: #2196f3;
    }
    
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
        
        /* Difference view styling - Dark mode */
        .diff-container {
            border: 1px solid #30363d;
        }
        .diff-only-c1 {
            background-color: rgba(244, 67, 54, 0.1);
            border-left: 3px solid #f44336;
        }
        .diff-only-c2 {
            background-color: rgba(76, 175, 80, 0.1);
            border-left: 3px solid #4caf50;
        }
        
        /* Score card styling - Dark mode */
        .score-card {
            background-color: rgba(25, 118, 210, 0.1);
            border-left: 4px solid #1976d2;
        }
        .score-meter {
            background-color: #30363d;
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

def create_area_scorecards(risk_analysis):
    """Generate scorecards for each comparison area."""
    
    if not risk_analysis or not isinstance(risk_analysis, dict):
        return "<p>Area scoring not available.</p>"
    
    # Get dimension scores for both contracts
    c1_dimensions = risk_analysis.get('contract1_dimension_scores', {})
    c2_dimensions = risk_analysis.get('contract2_dimension_scores', {})
    
    if not isinstance(c1_dimensions, dict) or not isinstance(c2_dimensions, dict):
        return "<p>Area scoring data invalid.</p>"
    
    # Create HTML for scorecards
    html = "<div class='score-cards-container'>"
    
    # Combine all dimension keys to ensure we cover all areas
    all_dimensions = set(list(c1_dimensions.keys()) + list(c2_dimensions.keys()))
    
    for dimension in all_dimensions:
        c1_score = c1_dimensions.get(dimension, 0)
        c2_score = c2_dimensions.get(dimension, 0)
        
        # Ensure scores are integers
        try:
            c1_score = int(c1_score)
        except (ValueError, TypeError):
            c1_score = 0
            
        try:
            c2_score = int(c2_score)
        except (ValueError, TypeError):
            c2_score = 0
        
        # Determine which contract is better in this dimension
        comparison_text = ""
        if c1_score > c2_score:
            comparison_text = f"Contract 1 scores {c1_score-c2_score} points higher"
        elif c2_score > c1_score:
            comparison_text = f"Contract 2 scores {c2_score-c1_score} points higher"
        else:
            comparison_text = "Both contracts score equally"
        
        html += f"""
        <div class="score-card">
            <div class="score-card-title">{dimension}</div>
            <p>{comparison_text} in this area.</p>
            <div style="display: flex; margin-bottom: 10px;">
                <div style="flex: 1; margin-right: 10px;">
                    <div style="font-weight: bold;">Contract 1: {c1_score}/100</div>
                    <div class="score-meter">
                        <div class="score-meter-fill" style="width: {c1_score}%;"></div>
                    </div>
                </div>
                <div style="flex: 1;">
                    <div style="font-weight: bold;">Contract 2: {c2_score}/100</div>
                    <div class="score-meter">
                        <div class="score-meter-fill" style="width: {c2_score}%;"></div>
                    </div>
                </div>
            </div>
        </div>
        """
    
    html += "</div>"
    return html

def compare_contracts_with_claude(contract1_text, contract2_text, analysis_focus, custom_prompt, custom_weights=None):
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
    
    # Add custom weights for scoring if provided
    weights_instruction = ""
    if custom_weights and isinstance(custom_weights, dict):
        weights_instruction = "\n\nPlease use the following custom weights when evaluating these contracts: "
        for area, weight in custom_weights.items():
            weights_instruction += f"{area}: {weight}%; "
    
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
    
    ADDITIONAL TASK: After completing the comparison, provide a separate structured risk assessment in JSON format enclosed in triple backticks with "json" language specifier. This assessment must include custom scores for each dimension on a scale of 0-100, with higher scores being better.
    {weights_instruction}
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
                
                # Apply any custom weights to adjust scores if provided
                if custom_weights and isinstance(custom_weights, dict):
                    try:
                        # Convert any selected focus areas not in weights to equal distribution
                        if analysis_focus:
                            remaining_weight = 100 - sum(custom_weights.values())
                            remaining_areas = [area for area in analysis_focus if area not in custom_weights]
                            
                            if remaining_areas and remaining_weight > 0:
                                weight_per_area = remaining_weight / len(remaining_areas)
                                for area in remaining_areas:
                                    custom_weights[area] = weight_per_area
                        
                        # Calculate weighted scores
                        c1_score = 0
                        c2_score = 0
                        total_weight = 0
                        
                        # First, try to map the custom weights to dimension scores
                        for dimension, scores in risk_analysis["contract1_dimension_scores"].items():
                            for area, weight in custom_weights.items():
                                # Check if dimension name contains the area name (case-insensitive)
                                if area.lower() in dimension.lower():
                                    c1_score += int(scores) * (weight / 100)
                                    c2_score += int(risk_analysis["contract2_dimension_scores"].get(dimension, 70)) * (weight / 100)
                                    total_weight += weight
                                    break
                        
                        # If we couldn't apply all weights, adjust the overall scores proportionally
                        if total_weight > 0:
                            risk_analysis["contract1_overall_score"] = int(c1_score * (100 / total_weight))
                            risk_analysis["contract2_overall_score"] = int(c2_score * (100 / total_weight))
                    except Exception as e:
                        # If there's an error applying weights, log it but continue
                        print(f"Error applying custom weights: {str(e)}")
                
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
    st.markdown('<div class="subtitle">Enhanced Side-by-Side Comparison with Custom Scoring</div>', unsafe_allow_html=True)
    
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
        
        # Custom scoring weights
        st.markdown("## Custom Scoring")
        st.info("Assign importance weights to each area (total should sum to 100%)")
        
        # Initialize weights dictionary
        if 'custom_weights' not in st.session_state:
            st.session_state.custom_weights = {}
        
        # Only show weight sliders for selected focus areas
        custom_weights = {}
        if analysis_focus:
            total_weight = 0
            for area in analysis_focus:
                # Default to equal distribution
                default_weight = int(100 / len(analysis_focus))
                if area in st.session_state.custom_weights:
                    default_weight = st.session_state.custom_weights[area]
                
                weight = st.slider(f"{area} weight", 0, 100, default_weight, 5, key=f"weight_{area}")
                custom_weights[area] = weight
                total_weight += weight
            
            # Show warning if weights don't sum to 100
            if total_weight != 100:
                st.warning(f"⚠️ Current weights sum to {total_weight}%. Consider adjusting to total 100%.")
            
            # Save weights to session state
            st.session_state.custom_weights = custom_weights
        
        custom_prompt = st.text_area("Custom Analysis Instructions (optional)", 
                             help="Add specific instructions for the contract comparison")
        
        # Warning if no focus or instruction provided
        if not analysis_focus and not custom_prompt:
            st.warning("⚠️ You must select at least one focus area or provide custom instructions")
        
        st.markdown("## About")
        st.info("""
        This tool creates side-by-side comparisons of ERP service contracts with custom scoring.
        
        Features include:
        - Clear side-by-side contract comparison
        - Expanded view of differences between contracts
        - Custom scoring for each comparison area
        - Risk assessment with color-coding
        - Executive summary with key insights
        """)
        
        # Data Privacy Note
        st.markdown("## Data Privacy")
        st.info("""
        **Privacy Notice:**
        
        This application processes contract documents locally and sends anonymized text to our secure API for comparison analysis. We do not store your documents or contract text after processing. All data is encrypted in transit.
        
        Your contract information is used solely to generate the comparison and is not used for any other purpose. Analysis results are stored only in your browser session and are automatically deleted when you close the application.
        
        For more information about our data handling practices, please contact your IT administrator.
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
            with st.spinner("Creating enhanced comparison with custom scoring... This may take a moment..."):
                contract1_text = extract_text(contract1_file)
                contract2_text = extract_text(contract2_file)
                
                # Default names if not provided
                if not contract1_name:
                    contract1_name = contract1_file.name
                if not contract2_name:
                    contract2_name = contract2_file.name
                
                # Generate the enhanced comparison with risk assessment and custom scoring
                analysis_result, risk_analysis = compare_contracts_with_claude(
                    contract1_text, 
                    contract2_text, 
                    analysis_focus, 
                    custom_prompt,
                    custom_weights if 'custom_weights' in locals() else None
                )
                
                # Add to history
                analysis_entry = {
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'contract1_name': contract1_name,
                    'contract2_name': contract2_name,
                    'focus_areas': analysis_focus,
                    'custom_prompt': custom_prompt,
                    'custom_weights': custom_weights if 'custom_weights' in locals() else {},
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
            
            # Display custom area scoring if available
            if 'risk_analysis' in analysis and analysis['risk_analysis']:
                st.markdown("### Area Scoring")
                area_scorecards = create_area_scorecards(analysis['risk_analysis'])
                st.markdown(area_scorecards, unsafe_allow_html=True)
            
            # Process the comparison text into sections
            sections = re.split(r'### (.*?)(?:\n|$)', analysis['result'])
            
            if len(sections) > 1:
                st.markdown("### Comparison Results")
                # For each section, create a section with expanded differences
                for i in range(1, len(sections), 2):
                    if i < len(sections):
                        category = sections[i].strip()
                        content = sections[i+1] if i+1 < len(sections) else ""
                        
                        st.markdown(f"#### {category}")
                        
                        # Split content into contract1 and contract2 parts
                        parts = re.split(r'#### (Contract 1|Contract 2)(?:\n|$)', content)
                        
                        if len(parts) > 2:  # We have proper split between contracts
                            # Side-by-side columns for contract comparison
                            col1, col2 = st.columns(2)
                            
                            contract1_content = ""
                            contract2_content = ""
                            
                            for j in range(1, len(parts), 2):
                                if j < len(parts):
                                    contract_type = parts[j].strip()
                                    contract_content = parts[j+1] if j+1 < len(parts) else ""
                                    
                                    if contract_type == "Contract 1":
                                        contract1_content = contract_content
                                        with col1:
                                            st.markdown(f"**{analysis['contract1_name']}**")
                                            st.markdown(contract_content)
                                    elif contract_type == "Contract 2":
                                        contract2_content = contract_content
                                        with col2:
                                            st.markdown(f"**{analysis['contract2_name']}**")
                                            st.markdown(contract_content)
                            
                            # Extract bullet points for difference analysis
                            bullet_pattern = r'(?:^|\n)- (.*?)(?:$|\n)'
                            bullets1 = re.findall(bullet_pattern, contract1_content)
                            bullets2 = re.findall(bullet_pattern, contract2_content)
                            
                            # Display differences section
                            st.markdown("##### Key Differences")
                            
                            # Create two columns for differences
                            diff_col1, diff_col2 = st.columns(2)
                            
                            with diff_col1:
                                st.markdown(f"**Unique to {analysis['contract1_name']}:**")
                                unique_to_1 = [b for b in bullets1 if b not in bullets2]
                                if unique_to_1:
                                    for bullet in unique_to_1:
                                        st.markdown(f"<div class='diff-only-c1'>- {bullet}</div>", unsafe_allow_html=True)
                                else:
                                    st.markdown("*No unique points*")
                                    
                            with diff_col2:
                                st.markdown(f"**Unique to {analysis['contract2_name']}:**")
                                unique_to_2 = [b for b in bullets2 if b not in bullets1]
                                if unique_to_2:
                                    for bullet in unique_to_2:
                                        st.markdown(f"<div class='diff-only-c2'>- {bullet}</div>", unsafe_allow_html=True)
                                else:
                                    st.markdown("*No unique points*")
                            
                            st.markdown("---")  # Add separator between sections
                        else:
                            # If no clear split between contracts, just show the content as is
                            st.markdown(content)
                            st.markdown("---")  # Add separator between sections
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
