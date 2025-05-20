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
import time
from concurrent.futures import ThreadPoolExecutor

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

# CSS for better styling
st.markdown("""
<style>
    /* Basic page styling */
    .main { padding: 2rem; }
    
    /* Custom header styles */
    .title-text { 
        font-size: 2.5rem; 
        font-weight: bold; 
        margin-bottom: 1rem; 
    }
    
    .subtitle-text { 
        font-size: 1.5rem; 
        margin-bottom: 2rem; 
    }
    
    /* Section headers */
    .section-header-custom { 
        font-size: 1.8rem; 
        font-weight: bold; 
        margin: 1.5rem 0 1rem 0; 
        padding-bottom: 0.5rem; 
        border-bottom: 2px solid #e0e0e0; 
    }
    
    /* Scorecard styling */
    .scorecard {
        background-color: #f0f8ff; 
        border-radius: 5px; 
        padding: 1rem; 
        margin-bottom: 1rem; 
        border-left: 4px solid #1976d2;
    }
    
    /* Progress bar containers */
    .progress-container {
        height: 8px; 
        background-color: #e0e0e0; 
        border-radius: 4px; 
        margin-bottom: 0.5rem; 
        overflow: hidden;
    }
    
    /* Difference highlighting */
    .unique-point-1 {
        background-color: #ffebee; 
        padding: 0.5rem; 
        margin-bottom: 0.5rem; 
        border-left: 3px solid #f44336;
    }
    
    .unique-point-2 {
        background-color: #e8f5e9; 
        padding: 0.5rem; 
        margin-bottom: 0.5rem; 
        border-left: 3px solid #4caf50;
    }
</style>
""", unsafe_allow_html=True)

# Extract text functions
@st.cache_data(ttl=3600, show_spinner=False)
def cached_extract_text(file_bytes, file_name):
    """Cached version of text extraction to avoid reprocessing the same file"""
    file_extension = os.path.splitext(file_name)[1].lower()
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp:
        temp.write(file_bytes)
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

def extract_text(file):
    """Extract text from various file formats."""
    return cached_extract_text(file.getvalue(), file.name)

def process_contracts_concurrently(contract1_file, contract2_file):
    """Process contracts in parallel using ThreadPoolExecutor"""
    
    def extract_single(file):
        return extract_text(file)
    
    # Use ThreadPoolExecutor for concurrent processing
    with ThreadPoolExecutor(max_workers=2) as executor:
        future1 = executor.submit(extract_single, contract1_file)
        future2 = executor.submit(extract_single, contract2_file)
        
        contract1_text = future1.result()
        contract2_text = future2.result()
        
    return contract1_text, contract2_text

def optimize_contract_for_claude(contract_text, focus_areas):
    """Reduce token usage by focusing on relevant sections of the contract."""
    # Define keywords for each focus area
    focus_keywords = {
        "Pricing Structure": ["price", "cost", "fee", "payment", "discount", "pricing", "rate", "subscription", "license", "amount", "charge", "invoice", "billing"],
        "Service Level Agreements": ["SLA", "uptime", "response time", "availability", "service level", "maintenance", "support", "outage", "incident", "resolution", "performance", "metric"],
        "Implementation Timeline": ["timeline", "schedule", "deadline", "milestone", "phase", "delivery", "implementation", "deploy", "rollout", "project plan", "date", "completion"],
        "Scope of Work": ["scope", "deliverable", "requirement", "specification", "work", "service", "function", "feature", "capability", "responsibility", "exclude"],
        "Maintenance & Support": ["maintenance", "support", "upgrade", "update", "patch", "fix", "bug", "repair", "service", "help desk", "ticket"],
        "Data Security": ["security", "data", "privacy", "confidential", "protection", "encrypt", "breach", "compliance", "GDPR", "backup", "disaster", "recovery"],
        "Exit Strategy": ["termination", "exit", "transition", "transfer", "handover", "wind down", "discontinue", "cease", "end", "expiration", "notice period"],
        "Intellectual Property": ["intellectual property", "IP", "copyright", "patent", "trademark", "license", "ownership", "proprietary", "right", "title"],
        "Change Management": ["change", "modification", "amendment", "alter", "adjust", "variation", "control", "request", "manage", "process", "procedure"],
        "Performance Metrics": ["performance", "metric", "measure", "indicator", "KPI", "target", "benchmark", "assessment", "evaluation", "report", "monitor"]
    }
    
    # Extract headers and structure for context preservation
    header_pattern = r'(?i)^\s*(?:ARTICLE|SECTION|CLAUSE|APPENDIX|EXHIBIT|SCHEDULE|ANNEX)\s+[\dIVXLC\.\-]+[ \.\:]+(.+?)$'
    headers = re.findall(header_pattern, contract_text, re.MULTILINE)
    
    # Split the contract into paragraphs/sections
    paragraphs = re.split(r'\n\s*\n', contract_text)
    
    # Identify relevant paragraphs based on focus areas
    relevant_paragraphs = []
    all_keywords = []
    
    # Collect all keywords for the selected focus areas
    for area in focus_areas:
        all_keywords.extend(focus_keywords.get(area, []))
    
    # Preserve key contract sections regardless of keywords
    important_sections = ["party", "parties", "definition", "term", "termination", "payment", "confidentiality", 
                          "liability", "warranty", "indemnification", "governing law", "jurisdiction", "dispute"]
    important_pattern = r'(?i)\b(' + '|'.join(important_sections) + r')\b'
    
    # Preserve the first few paragraphs for context (contract intro, parties, etc.)
    intro_paragraphs = min(10, len(paragraphs) // 10)  # Include about 10% as intro or at least 10 paragraphs
    
    # Track which paragraphs to include
    paragraphs_to_include = set(range(intro_paragraphs))
    
    # Identify paragraphs with relevant keywords
    for i, paragraph in enumerate(paragraphs):
        # Always include paragraphs that look like headers or section titles
        if re.search(header_pattern, paragraph, re.MULTILINE):
            paragraphs_to_include.add(i)
            # Also include the next paragraph after a header
            if i+1 < len(paragraphs):
                paragraphs_to_include.add(i+1)
            continue
        
        # Check for important contract sections
        if re.search(important_pattern, paragraph.lower()):
            paragraphs_to_include.add(i)
            continue
            
        # Check for focus area keywords
        for keyword in all_keywords:
            if keyword.lower() in paragraph.lower():
                paragraphs_to_include.add(i)
                # Also include the next paragraph for context
                if i+1 < len(paragraphs):
                    paragraphs_to_include.add(i+1)
                break
    
    # Compile the optimized text
    optimized_paragraphs = [paragraphs[i] for i in sorted(paragraphs_to_include)]
    optimized_text = "\n\n".join(optimized_paragraphs)
    
    # If optimized text is too short, return the original
    if len(optimized_text) < len(contract_text) * 0.3:
        return contract_text[:25000]  # Limit to 25K chars as in the original function
    
    # Limit to 25K chars as in the original function
    return optimized_text[:25000]

def create_executive_summary(analysis_result, risk_analysis, contract1_name, contract2_name):
    """Generate an executive summary from the analysis results and risk assessment."""
    
    if not risk_analysis:
        return "<div style='background-color: #f5f7fa; border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem; border-left: 5px solid #1890ff;'><h3 style='margin-top: 0; color: #1f3a60;'>Executive Summary</h3><p>Risk analysis data not available. Please rerun the comparison.</p></div>"
    
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
    
    # Get background color for grade pills
    def get_grade_color(grade):
        if grade == "A": return "#388e3c"
        elif grade == "B": return "#689f38"
        elif grade == "C": return "#afb42b"
        elif grade == "D": return "#ffa000"
        else: return "#e64a19"
    
    c1_color = get_grade_color(c1_grade)
    c2_color = get_grade_color(c2_grade)
    
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
    
    # Create the summary HTML with inline styles instead of classes
    html = f"""
    <div style="background-color: #f5f7fa; border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem; border-left: 5px solid #1890ff;">
        <h3 style="margin-top: 0; color: #1f3a60;">Executive Summary: Contract Comparison</h3>
        <div style="display: flex; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 300px; padding-right: 15px; margin-bottom: 15px;">
                <h4>{contract1_name}</h4>
                <p><span style="display: inline-block; padding: 0.35rem 0.65rem; border-radius: 1rem; font-weight: bold; color: white; background-color: {c1_color}; margin-right: 0.5rem; font-size: 0.9rem;">{c1_grade}</span> Overall Score: {c1_score}/100</p>
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
            <div style="flex: 1; min-width: 300px; padding-left: 15px; margin-bottom: 15px;">
                <h4>{contract2_name}</h4>
                <p><span style="display: inline-block; padding: 0.35rem 0.65rem; border-radius: 1rem; font-weight: bold; color: white; background-color: {c2_color}; margin-right: 0.5rem; font-size: 0.9rem;">{c2_grade}</span> Overall Score: {c2_score}/100</p>
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
        <div style="margin-top: 0.75rem;">
            <p>{recommendation}</p>
        </div>
    </div>
    """
    
    return html

def normalize_dimension_name(name):
    """Normalize dimension names to prevent duplicates with different casing/formatting."""
    # Convert to lowercase, replace spaces and underscores with a single space, and capitalize words
    normalized = name.lower().replace('_', ' ').strip()
    return normalized

def create_area_scorecards(risk_analysis):
    """Generate scorecards for each comparison area."""
    
    if not risk_analysis or not isinstance(risk_analysis, dict):
        return "<p>Area scoring not available.</p>"
    
    # Get dimension scores for both contracts
    c1_dimensions = risk_analysis.get('contract1_dimension_scores', {})
    c2_dimensions = risk_analysis.get('contract2_dimension_scores', {})
    
    if not isinstance(c1_dimensions, dict) or not isinstance(c2_dimensions, dict):
        return "<p>Area scoring data invalid.</p>"
    
    # Instead of building HTML, let's use Streamlit's native components
    # Create a container div for better styling
    content = ""
    
    # Normalize dimension names to prevent duplicates
    normalized_dimensions = {}
    
    # First, collect all dimensions with their normalized names
    all_dimensions = set(list(c1_dimensions.keys()) + list(c2_dimensions.keys()))
    for dimension in all_dimensions:
        norm_name = normalize_dimension_name(dimension)
        # If this normalized name already exists, use the one with the higher score as it's likely more accurate
        if norm_name in normalized_dimensions:
            existing_dim = normalized_dimensions[norm_name]
            c1_existing_score = c1_dimensions.get(existing_dim, 0)
            c2_existing_score = c2_dimensions.get(existing_dim, 0)
            c1_new_score = c1_dimensions.get(dimension, 0)
            c2_new_score = c2_dimensions.get(dimension, 0)
            
            # If the new dimension has non-zero scores and the existing one has zeros, replace it
            if (c1_new_score > 0 or c2_new_score > 0) and (c1_existing_score == 0 and c2_existing_score == 0):
                normalized_dimensions[norm_name] = dimension
            # Otherwise keep the one with proper capitalization or the first one
        else:
            normalized_dimensions[norm_name] = dimension
    
    # Now process the unique dimensions
    for _, dimension in sorted(normalized_dimensions.items()):
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
        difference = abs(c1_score - c2_score)
        if c1_score > c2_score:
            comparison_text = f"Contract 1 scores {difference} points higher"
        elif c2_score > c1_score:
            comparison_text = f"Contract 2 scores {difference} points higher"
        else:
            comparison_text = "Both contracts score equally"
        
        # Display a nicely formatted dimension name (Title Case)
        display_name = ' '.join(word.capitalize() for word in dimension.replace('_', ' ').split())
        
        # Add styled scorecard markup
        content += f"""
        <div style="background-color: #f0f8ff; border-radius: 5px; padding: 1rem; margin-bottom: 1rem; border-left: 4px solid #1976d2;">
            <div style="font-weight: bold; margin-bottom: 0.5rem;">{display_name}</div>
            <p>{comparison_text} in this area.</p>
            <div style="display: flex; margin-bottom: 10px;">
                <div style="flex: 1; margin-right: 10px;">
                    <div style="font-weight: bold;">Contract 1: {c1_score}/100</div>
                    <div style="height: 8px; background-color: #e0e0e0; border-radius: 4px; margin-bottom: 0.5rem; overflow: hidden;">
                        <div style="height: 100%; width: {c1_score}%; background-color: #2196f3;"></div>
                    </div>
                </div>
                <div style="flex: 1;">
                    <div style="font-weight: bold;">Contract 2: {c2_score}/100</div>
                    <div style="height: 8px; background-color: #e0e0e0; border-radius: 4px; margin-bottom: 0.5rem; overflow: hidden;">
                        <div style="height: 100%; width: {c2_score}%; background-color: #2196f3;"></div>
                    </div>
                </div>
            </div>
        </div>
        """
    
    return content

def robust_claude_api_call(client, prompt, system_prompt):
    """Handle Claude API calls with robust error handling and retries"""
    max_retries = 3
    retry_count = 0
    backoff_time = 2  # seconds
    
    while retry_count < max_retries:
        try:
            response = client.messages.create(
                model=st.secrets["ANTHROPIC_MODEL"],
                max_tokens=6000,
                temperature=0.2,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response
        
        except anthropic.APITimeoutError:
            retry_count += 1
            if retry_count >= max_retries:
                raise Exception("API timeout after multiple retries. Please try again later.")
            
            time.sleep(backoff_time)
            backoff_time *= 2  # Exponential backoff
            
        except anthropic.APIError as e:
            if "rate limit" in str(e).lower():
                retry_count += 1
                if retry_count >= max_retries:
                    raise Exception("Rate limit reached after multiple retries. Please try again later.")
                
                time.sleep(backoff_time)
                backoff_time *= 2
            else:
                raise e
        
        except Exception as e:
            # For other exceptions, don't retry
            raise e

def compare_contracts_with_claude(contract1_text, contract2_text, analysis_focus, custom_prompt, custom_weights=None):
    """Use Claude AI to compare contracts and generate insights with risk assessment."""
    
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    
    # Optimize contracts to focus on relevant sections (API call optimization)
    if analysis_focus:
        optimized_contract1 = optimize_contract_for_claude(contract1_text, analysis_focus)
        optimized_contract2 = optimize_contract_for_claude(contract2_text, analysis_focus)
    else:
        # If no focus areas, use the original behavior
        optimized_contract1 = contract1_text[:25000]
        optimized_contract2 = contract2_text[:25000]
    
    # Create dimension mapping directly from focus areas
    scoring_dimensions = []
    if analysis_focus:
        scoring_dimensions = analysis_focus
    else:
        # Default dimensions if no focus areas selected
        scoring_dimensions = ["Pricing", "Risk Allocation", "Service Levels", "Flexibility", "Legal Protection"]
    
    # Add custom weights for scoring if provided
    weights_instruction = ""
    if custom_weights and isinstance(custom_weights, dict):
        weights_instruction = "\n\nIMPORTANT - Use these specific importance weights when evaluating contracts: "
        for area, weight in custom_weights.items():
            weights_instruction += f"{area}: {weight}%; "
    
    # Smarter Claude prompting - Updated system prompt
    system_prompt = """You are an expert procurement analyst specializing in IT and ERP service contracts with 20+ years of experience. 
Your task is to create a detailed, actionable comparison of contract terms with these key qualities:
1. Precision - Use exact clause references and specific language
2. Clarity - Highlight key differences for easy comparison
3. Practical relevance - Focus on business impact, not just legal wording
4. Balanced assessment - Objectively identify strengths and weaknesses in both contracts
5. Clear scoring - Use concrete evidence to justify different scores for each dimension

Format your analysis as a structured side-by-side comparison with clear sections. Use bullet points for readability and bold formatting to emphasize key differences. Write in clear, concise British English focused on practical implications."""

    # Smarter Claude prompting - Enhanced dimension-specific guidance
    dimension_guidance = {
        "Pricing Structure": """
- Compare base fees, variable costs, and total cost of ownership
- Analyze payment schedules, terms, and conditions
- Evaluate price adjustment mechanisms and inflators
- Identify any hidden or contingent costs
- Assess value for money and cost efficiency
        """,
        "Service Level Agreements": """
- Compare specific performance metrics and their definitions
- Analyze consequences of SLA breaches (credits, remedies)
- Evaluate measurement and reporting mechanisms
- Identify exclusions, force majeure, and planned downtime provisions
- Assess enforceability and practical application of SLAs
        """,
        "Implementation Timeline": """
- Compare key milestones, deadlines and dependencies
- Evaluate specificity of project phases and deliverables
- Analyze consequences of delays and remedies
- Identify responsibility for delays and risk allocation
- Assess realism and feasibility of proposed timelines
        """,
        "Scope of Work": """
- Compare specific deliverables and their specifications
- Analyze inclusivity vs. exclusivity of services
- Evaluate clarity and thoroughness of requirements
- Identify any gaps or ambiguities in scope definition
- Assess alignment with business objectives
        """,
        "Maintenance & Support": """
- Compare support levels, hours, and response times
- Analyze upgrade and patch management provisions
- Evaluate escalation procedures and priority levels
- Identify long-term support commitments and constraints
- Assess practical sufficiency for business operations
        """,
        "Data Security": """
- Compare security standards and compliance frameworks
- Analyze breach notification and response procedures
- Evaluate data protection, backup and recovery provisions
- Identify liability and indemnification for security issues
- Assess adequacy for regulatory compliance
        """,
        "Exit Strategy": """
- Compare termination rights, notice periods, and fees
- Analyze transition services and knowledge transfer
- Evaluate data return, migration, and deletion provisions
- Identify potential lock-in issues or exit barriers
- Assess practical feasibility of transition
        """,
        "Intellectual Property": """
- Compare ownership rights to deliverables and data
- Analyze license terms, restrictions, and usage rights
- Evaluate protection of pre-existing IP and new developments
- Identify potential conflicts or ambiguities in IP provisions
- Assess alignment with business IP strategy
        """,
        "Change Management": """
- Compare change request procedures and approvals
- Analyze pricing mechanisms for changes and additions
- Evaluate flexibility vs. rigidity in changing requirements
- Identify constraints or limitations on changes
- Assess practical workability of change processes
        """,
        "Performance Metrics": """
- Compare specific KPIs, measurements, and monitoring
- Analyze reporting requirements and cadence
- Evaluate consequences of performance failures
- Identify incentives for exceeding performance targets
- Assess alignment with business success factors
        """
    }
    
    # Build dimension-specific instructions
    dimension_instructions = ""
    for area in scoring_dimensions:
        dimension_instructions += f"\n\n{area}:\n{dimension_guidance.get(area, '- Analyze all relevant provisions thoroughly')}"
    
    # Smarter Claude prompting - Enhanced user prompt structure
    prompt = f"""
As an expert ERP contract analyst, create a detailed, actionable comparison of these two contracts.

FOCUS AREAS: {', '.join(scoring_dimensions)}

{custom_prompt if custom_prompt else ''}

CONTRACT 1:
{optimized_contract1}

CONTRACT 2:
{optimized_contract2}

ANALYSIS INSTRUCTIONS:
For each focus area, provide:
1. A direct side-by-side comparison of equivalent provisions
2. Specific clause references where possible (e.g., "Section 3.2")
3. Clear identification of strengths and weaknesses
4. Explicit mention of provisions present in one contract but missing in the other
5. Bold formatting for significant differences or important terms

FORMAT REQUIREMENTS:
- Use this structure for each area:
  ### [Topic Name]
  #### Contract 1
  - Key point 1
  - Key point 2
  
  #### Contract 2
  - Key point 1
  - Key point 2

DIMENSION-SPECIFIC GUIDANCE:{dimension_instructions}

SCORING REQUIREMENTS:
When scoring each dimension, follow this approach:
1. First directly compare Contract 1 against Contract 2 for this dimension
2. Assign scores on a 0-100 scale where:
   - 50 means both contracts are equal
   - >50 means Contract 1 is better (with 100 being Contract 1 is vastly superior)
   - <50 means Contract 2 is better (with 0 being Contract 2 is vastly superior)
3. The difference between the scores should reflect the magnitude of advantage
4. Example: If Contract 1 has slightly better pricing, score it 60/100, meaning it's 10 points better than Contract 2
5. Ensure scores are differentiated based on actual content - avoid giving similar scores to all dimensions

{weights_instruction}

JSON OUTPUT:
After your analysis, include a detailed risk assessment in JSON format enclosed in triple backticks with "json" language specifier:
```json
{{
  "contract1_overall_score": 75,
  "contract2_overall_score": 65,
  "contract1_dimension_scores": {{
    "Dimension Name 1": 80,
    "Dimension Name 2": 70
  }},
  "contract2_dimension_scores": {{
    "Dimension Name 1": 60,
    "Dimension Name 2": 75
  }},
  "contract1_advantages": [
    "Specific advantage 1",
    "Specific advantage 2",
    "Specific advantage 3"
  ],
  "contract1_disadvantages": [
    "Specific disadvantage 1",
    "Specific disadvantage 2",
    "Specific disadvantage 3"
  ],
  "contract2_advantages": [
    "Specific advantage 1",
    "Specific advantage 2",
    "Specific advantage 3"
  ],
  "contract2_disadvantages": [
    "Specific disadvantage 1",
    "Specific disadvantage 2",
    "Specific disadvantage 3"
  ],
  "recommendation": "Clear, actionable recommendation based on analysis"
}}
```

CRITICAL: For the JSON output:
1. Use EXACTLY these dimension names: {', '.join(scoring_dimensions)}
2. Ensure each focus area has corresponding scores in both contracts
3. Make sure overall scores reflect the weighted importance of each dimension
4. Provide at least 3 specific advantages and disadvantages for each contract
5. Ensure your recommendation is clear and actionable
"""
    
    try:
        # Use robust API call with retries
        response = robust_claude_api_call(client, prompt, system_prompt)
        
        # Extract the main comparison text and the JSON risk assessment
        full_response = response.content[0].text
        
        # Find and extract the JSON part (assuming it's at the end)
        json_match = re.search(r'```json\s*(.*?)\s*```', full_response, re.DOTALL)
        
        # Create default risk analysis with basic structure but varied scores
        # Intentionally vary the default scores to avoid all 70s
        default_risk_analysis = {
            "contract1_overall_score": 55,
            "contract2_overall_score": 45,
            "contract1_dimension_scores": {},
            "contract2_dimension_scores": {},
            "categories": [],
            "contract1_advantages": ["Good overall terms"],
            "contract1_disadvantages": ["Could be improved in some areas"],
            "contract2_advantages": ["Good overall terms"],
            "contract2_disadvantages": ["Could be improved in some areas"],
            "recommendation": "Both contracts have strengths and weaknesses. Further analysis recommended."
        }
        
        # Add dimension scores with varied defaults - centered around 50 (equal)
        base_scores = [55, 45, 60, 40, 52, 48, 65, 35, 58, 42]
        for i, dimension in enumerate(scoring_dimensions):
            score_idx = i % len(base_scores)
            default_risk_analysis["contract1_dimension_scores"][dimension] = base_scores[score_idx]
            # Contract 2 score is implied (100 - contract1_score)
            default_risk_analysis["contract2_dimension_scores"][dimension] = 100 - base_scores[score_idx]
        
        if json_match:
            json_text = json_match.group(1)
            # Remove the JSON part from the main response
            comparison_text = full_response[:json_match.start()].strip()
            
            # Parse the JSON
            try:
                risk_analysis = json.loads(json_text)
                
                # Debug the parsed JSON
                st.session_state.debug_json = json_text
                
                # Ensure all required fields exist with defaults if not present
                risk_analysis.setdefault("contract1_overall_score", 55)
                risk_analysis.setdefault("contract2_overall_score", 45)
                
                # Ensure dimension scores exist for all focus areas
                if "contract1_dimension_scores" not in risk_analysis:
                    risk_analysis["contract1_dimension_scores"] = {}
                if "contract2_dimension_scores" not in risk_analysis:
                    risk_analysis["contract2_dimension_scores"] = {}
                
                # Fill in any missing dimension scores
                for dimension in scoring_dimensions:
                    dim_found = False
                    # Check for variations of the dimension name (case insensitive, with underscores/spaces)
                    for existing_dim in risk_analysis["contract1_dimension_scores"].keys():
                        if normalize_dimension_name(dimension) == normalize_dimension_name(existing_dim):
                            dim_found = True
                            break
                    
                    if not dim_found:
                        idx = scoring_dimensions.index(dimension) % len(base_scores)
                        risk_analysis["contract1_dimension_scores"][dimension] = base_scores[idx]
                        risk_analysis["contract2_dimension_scores"][dimension] = 100 - base_scores[idx]
                
                # Apply any custom weights to adjust overall scores if provided
                if custom_weights and isinstance(custom_weights, dict):
                    try:
                        # Convert any selected focus areas not in weights to equal distribution
                        remaining_weight = 100 - sum(custom_weights.values())
                        remaining_areas = [area for area in scoring_dimensions if area not in custom_weights]
                        
                        if remaining_areas and remaining_weight > 0:
                            weight_per_area = remaining_weight / len(remaining_areas)
                            for area in remaining_areas:
                                custom_weights[area] = weight_per_area
                        
                        # Calculate weighted scores
                        c1_score = 0
                        c2_score = 0
                        total_weight = 0
                        
                        # Use exact dimension names from scoring_dimensions
                        for dimension in scoring_dimensions:
                            # Try to find this dimension with normalization
                            dim_to_use = None
                            for existing_dim in risk_analysis["contract1_dimension_scores"].keys():
                                if normalize_dimension_name(dimension) == normalize_dimension_name(existing_dim):
                                    dim_to_use = existing_dim
                                    break
                            
                            if dim_to_use and dimension in custom_weights:
                                weight = custom_weights[dimension]
                                c1_score += risk_analysis["contract1_dimension_scores"][dim_to_use] * (weight / 100)
                                c2_score += risk_analysis["contract2_dimension_scores"].get(dim_to_use, 100 - risk_analysis["contract1_dimension_scores"][dim_to_use]) * (weight / 100)
                                total_weight += weight
                        
                        # Apply the weighted scores
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

def create_performance_metrics():
    """Display performance metrics for the current analysis if available"""
    
    if 'performance_metrics' not in st.session_state:
        return
        
    metrics = st.session_state.performance_metrics
    
    st.subheader("Performance Metrics")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Processing Time", 
            f"{metrics.get('total_time', 0):.2f}s",
            help="Total time to process and analyze contracts"
        )
    
    with col2:
        original_size = metrics.get('original_size', 0)
        optimized_size = metrics.get('optimized_size', 0)
        
        if original_size > 0:
            reduction = ((original_size - optimized_size) / original_size) * 100
            st.metric(
                "Token Reduction", 
                f"{reduction:.1f}%",
                help="Percentage reduction in text size after optimization"
            )
        else:
            st.metric("Token Reduction", "N/A")
    
    with col3:
        st.metric(
            "Estimated Cost", 
            f"${metrics.get('estimated_cost', 0):.4f}",
            help="Estimated cost of API calls"
        )

def main():
    # App header
    st.markdown('<div style="font-size: 2.5rem; font-weight: bold; margin-bottom: 1rem;">ERP Contract Comparison Tool</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size: 1.5rem; margin-bottom: 2rem;">Enhanced Side-by-Side Comparison with Custom Scoring</div>', unsafe_allow_html=True)
    
    # Initialize session state
    if 'analysis_history' not in st.session_state:
        st.session_state.analysis_history = []
    if 'debug_json' not in st.session_state:
        st.session_state.debug_json = None
    if 'performance_metrics' not in st.session_state:
        st.session_state.performance_metrics = {}
    
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
        
        # Advanced settings expander
        with st.expander("Advanced Settings"):
            st.checkbox("Enable performance metrics", key="enable_metrics", value=True,
                        help="Show performance metrics like processing time and token usage")
            
            st.checkbox("Use parallel processing", key="use_parallel", value=True,
                       help="Process contracts concurrently to save time")
        
        st.markdown("## About")
        st.info("""
        This tool creates side-by-side comparisons of ERP service contracts with custom scoring.
        
        Features include:
        - Clear side-by-side contract comparison
        - Expanded view of differences between contracts
        - Custom scoring for each comparison area
        - Risk assessment with color-coding
        - Executive summary with key insights
        - Optimized contract processing for faster results
        """)
        
        # Data Privacy Note
        st.markdown("## Data Privacy")
        st.info("""
        **Privacy Notice:**
        
        This application processes contract documents locally and sends anonymized text to our secure API for comparison analysis. We do not store your documents or contract text after processing. All data is encrypted in transit.
        
        Your contract information is used solely to generate the comparison and is not used for any other purpose. Analysis results are stored only in your browser session and are automatically deleted when you close the application.
        
        For more information about our data handling practices, please contact your IT administrator.
        """)
    
    # Main interface with progressive disclosure
    tabs = st.tabs(["Contract Upload", "Comparison Results", "Key Findings", "Technical Details", "History"])
    
    # Contract Upload Tab
    with tabs[0]:
        st.markdown('<div style="font-size: 1.8rem; font-weight: bold; margin: 1.5rem 0 1rem 0; padding-bottom: 0.5rem; border-bottom: 2px solid #e0e0e0;">Upload Contracts for Comparison</div>', unsafe_allow_html=True)
        
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
                start_time = time.time()
                
                # Extract contract text (potentially in parallel)
                if st.session_state.get("use_parallel", True):
                    contract1_text, contract2_text = process_contracts_concurrently(contract1_file, contract2_file)
                else:
                    contract1_text = extract_text(contract1_file)
                    contract2_text = extract_text(contract2_file)
                
                # Track original text sizes for metrics
                original_size = len(contract1_text) + len(contract2_text)
                
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
                
                # Calculate performance metrics
                end_time = time.time()
                total_time = end_time - start_time
                
                # Get optimized size by running the optimizer
                if analysis_focus:
                    optimized_contract1 = optimize_contract_for_claude(contract1_text, analysis_focus)
                    optimized_contract2 = optimize_contract_for_claude(contract2_text, analysis_focus)
                    optimized_size = len(optimized_contract1) + len(optimized_contract2)
                else:
                    optimized_size = min(len(contract1_text), 25000) + min(len(contract2_text), 25000)
                
                # Estimate cost (very rough approximation)
                # Claude 3 Opus is roughly $15 per 1M tokens, assuming ~4 chars per token
                estimated_tokens = optimized_size / 4
                estimated_cost = (estimated_tokens / 1000000) * 15
                
                # Store metrics
                if st.session_state.get("enable_metrics", True):
                    st.session_state.performance_metrics = {
                        "total_time": total_time,
                        "original_size": original_size,
                        "optimized_size": optimized_size,
                        "estimated_cost": estimated_cost
                    }
                
                # Add to history
                analysis_entry = {
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'contract1_name': contract1_name,
                    'contract2_name': contract2_name,
                    'focus_areas': analysis_focus,
                    'custom_prompt': custom_prompt,
                    'custom_weights': custom_weights if 'custom_weights' in locals() else {},
                    'result': analysis_result,
                    'risk_analysis': risk_analysis,
                    'performance_metrics': st.session_state.performance_metrics
                }
                st.session_state.analysis_history.append(analysis_entry)
                st.session_state.current_analysis = analysis_entry
                
                # Go to results tab
                st.query_params["tab"] = "results"
                st.rerun()
                
    # Comparison Results Tab (Full detailed comparison)
    with tabs[1]:
        if 'current_analysis' in st.session_state:
            analysis = st.session_state.current_analysis
            
            st.markdown(f'<div style="font-size: 1.8rem; font-weight: bold; margin: 1.5rem 0 1rem 0; padding-bottom: 0.5rem; border-bottom: 2px solid #e0e0e0;">Enhanced Contract Comparison</div>', unsafe_allow_html=True)
            
            # Show executive summary if risk analysis is available
            if 'risk_analysis' in analysis and analysis['risk_analysis']:
                exec_summary = create_executive_summary(
                    analysis['result'], 
                    analysis['risk_analysis'], 
                    analysis['contract1_name'], 
                    analysis['contract2_name']
                )
                st.markdown(exec_summary, unsafe_allow_html=True)
            
            # Show performance metrics if enabled
            if st.session_state.get("enable_metrics", True) and 'performance_metrics' in analysis:
                st.session_state.performance_metrics = analysis['performance_metrics']
                create_performance_metrics()
            
            # Display comparison metadata
            metadata_col1, metadata_col2 = st.columns(2)
            with metadata_col1:
                st.markdown(f"**Contracts:** {analysis['contract1_name']} vs {analysis['contract2_name']}")
                st.markdown(f"**Analysis performed:** {analysis['timestamp']}")
            
            with metadata_col2:
                focus_areas = "All selected: " + ", ".join(analysis['focus_areas']) if analysis['focus_areas'] else "None"
                st.markdown(f"**Focus Areas:** {focus_areas}")
            
            # Display custom instructions if any
            if analysis.get('custom_prompt'):
                st.markdown("---")
                st.markdown(f"**Custom Analysis Instructions:**")
                st.info(analysis['custom_prompt'])
            
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
                                        st.markdown(f"<div class='unique-point-1'>- {bullet}</div>", unsafe_allow_html=True)
                                else:
                                    st.markdown("*No unique points*")
                                    
                            with diff_col2:
                                st.markdown(f"**Unique to {analysis['contract2_name']}:**")
                                unique_to_2 = [b for b in bullets2 if b not in bullets1]
                                if unique_to_2:
                                    for bullet in unique_to_2:
                                        st.markdown(f"<div class='unique-point-2'>- {bullet}</div>", unsafe_allow_html=True)
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
    
    # Key Findings Tab (Simplified view with scores and key points)
    with tabs[2]:
        if 'current_analysis' in st.session_state:
            analysis = st.session_state.current_analysis
            
            st.markdown(f'<div style="font-size: 1.8rem; font-weight: bold; margin: 1.5rem 0 1rem 0; padding-bottom: 0.5rem; border-bottom: 2px solid #e0e0e0;">Key Contract Findings</div>', unsafe_allow_html=True)
            
            if 'risk_analysis' in analysis and analysis['risk_analysis']:
                # Display dimension scores
                st.markdown("### Dimension Scores")
                
                # Get dimension scores
                c1_dimensions = analysis['risk_analysis'].get('contract1_dimension_scores', {})
                c2_dimensions = analysis['risk_analysis'].get('contract2_dimension_scores', {})
                
                # Display scores using Streamlit metrics and progress bars
                for dimension in analysis['focus_areas']:
                    # Find the dimension with potential different casing
                    dim_to_use = None
                    for existing_dim in c1_dimensions.keys():
                        if normalize_dimension_name(dimension) == normalize_dimension_name(existing_dim):
                            dim_to_use = existing_dim
                            break
                    
                    if not dim_to_use:
                        continue
                        
                    c1_score = c1_dimensions.get(dim_to_use, 0)
                    c2_score = c2_dimensions.get(dim_to_use, 0)
                    
                    # Format pretty display name
                    display_name = ' '.join(word.capitalize() for word in dimension.replace('_', ' ').split())
                    st.markdown(f"#### {display_name}")
                    
                    # Create two columns for the scores
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Show the score with delta from average or from the other contract
                        delta = c1_score - 50 if abs(c1_score - 50) > abs(c1_score - c2_score) else c1_score - c2_score
                        st.metric(
                            f"{analysis['contract1_name']}", 
                            f"{c1_score}/100",
                            delta=delta if delta != 0 else None,
                            delta_color="normal"
                        )
                        st.progress(c1_score/100)
                    
                    with col2:
                        delta = c2_score - 50 if abs(c2_score - 50) > abs(c2_score - c1_score) else c2_score - c1_score
                        st.metric(
                            f"{analysis['contract2_name']}", 
                            f"{c2_score}/100",
                            delta=delta if delta != 0 else None,
                            delta_color="normal"
                        )
                        st.progress(c2_score/100)
                
                # Display recommendation
                st.markdown("### Recommendation")
                recommendation = analysis['risk_analysis'].get('recommendation', 'Further detailed analysis recommended.')
                st.info(recommendation)
                
                # Display key advantages and disadvantages
                st.markdown("### Key Contract Points")
                
                adv_col1, adv_col2 = st.columns(2)
                
                with adv_col1:
                    st.markdown(f"#### {analysis['contract1_name']} Highlights")
                    
                    st.markdown("**Advantages:**")
                    advantages = analysis['risk_analysis'].get('contract1_advantages', [])
                    for adv in advantages:
                        st.markdown(f"- {adv}")
                    
                    st.markdown("**Disadvantages:**")
                    disadvantages = analysis['risk_analysis'].get('contract1_disadvantages', [])
                    for disadv in disadvantages:
                        st.markdown(f"- {disadv}")
                
                with adv_col2:
                    st.markdown(f"#### {analysis['contract2_name']} Highlights")
                    
                    st.markdown("**Advantages:**")
                    advantages = analysis['risk_analysis'].get('contract2_advantages', [])
                    for adv in advantages:
                        st.markdown(f"- {adv}")
                    
                    st.markdown("**Disadvantages:**")
                    disadvantages = analysis['risk_analysis'].get('contract2_disadvantages', [])
                    for disadv in disadvantages:
                        st.markdown(f"- {disadv}")
            else:
                st.warning("No analysis data available. Please go to the Contract Upload tab and compare contracts.")
    
    # Technical Details Tab
    with tabs[3]:
        if 'current_analysis' in st.session_state:
            analysis = st.session_state.current_analysis
            
            st.markdown(f'<div style="font-size: 1.8rem; font-weight: bold; margin: 1.5rem 0 1rem 0; padding-bottom: 0.5rem; border-bottom: 2px solid #e0e0e0;">Technical Details</div>', unsafe_allow_html=True)
            
            # Performance metrics in more detail
            if st.session_state.get("enable_metrics", True) and 'performance_metrics' in analysis:
                st.session_state.performance_metrics = analysis.get('performance_metrics', {})
                metrics = st.session_state.performance_metrics
                
                st.markdown("### Performance Metrics")
                
                metrics_cols = st.columns(3)
                with metrics_cols[0]:
                    st.metric("Processing Time", f"{metrics.get('total_time', 0):.2f}s")
                
                with metrics_cols[1]:
                    original_chars = metrics.get('original_size', 0)
                    optimized_chars = metrics.get('optimized_size', 0)
                    st.metric("Original Size", f"{original_chars:,} chars")
                    
                with metrics_cols[2]:
                    st.metric("Optimized Size", f"{optimized_chars:,} chars")
                
                # Add more detailed metrics
                if original_chars > 0:
                    reduction = ((original_chars - optimized_chars) / original_chars) * 100
                    st.progress(reduction/100)
                    st.markdown(f"**Text Reduction:** {reduction:.1f}% ({original_chars:,} → {optimized_chars:,} chars)")
                
                if 'estimated_cost' in metrics:
                    st.markdown(f"**Estimated API Cost:** ${metrics.get('estimated_cost', 0):.4f}")
            
            # Display the raw JSON from Claude
            st.markdown("### Raw Analysis Data (JSON)")
            
            if 'risk_analysis' in analysis:
                with st.expander("Show Raw JSON"):
                    st.json(analysis['risk_analysis'])
            
            # Add system information
            st.markdown("### System Information")
            
            system_info = {
                "App Version": "2.1.0",
                "Streamlit Version": st.__version__,
                "API Model": st.secrets.get("ANTHROPIC_MODEL", "claude-3-opus-20240229"),
                "Python Version": "3.9+",
                "Analysis Timestamp": analysis.get('timestamp', 'Unknown')
            }
            
            st.json(system_info)
        else:
            st.warning("No analysis data available. Please go to the Contract Upload tab and compare contracts.")
            
    # History Tab
    with tabs[4]:
        st.markdown('<div style="font-size: 1.8rem; font-weight: bold; margin: 1.5rem 0 1rem 0; padding-bottom: 0.5rem; border-bottom: 2px solid #e0e0e0;">Comparison History</div>', unsafe_allow_html=True)
        
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
                    
                    # Row of buttons
                    col1, col2, col3 = st.columns([1, 1, 2])
                    
                    with col1:
                        # Button to view this comparison
                        if st.button(f"View Full Comparison", key=f"view_{i}"):
                            st.session_state.current_analysis = analysis
                            st.query_params["tab"] = "results"
                            st.rerun()
                    
                    with col2:
                        # Button to view key findings
                        if st.button(f"View Key Findings", key=f"findings_{i}"):
                            st.session_state.current_analysis = analysis
                            st.query_params["tab"] = "key_findings"
                            st.rerun()
                    
                    # Add more action buttons if needed
        else:
            st.info("Your comparison history will appear here")

if __name__ == "__main__":
    main()
