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
    /* Enhanced formatting for comparison table */
    .comparison-table { 
        width: 100%; 
        border-collapse: collapse; 
        margin: 1rem 0; 
        border: 1px solid #e0e0e0;
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
    .key-finding {
        font-weight: bold;
        color: #1890ff;
    }
    .alert-warning {
        color: #d63031;
        font-weight: bold;
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

def format_comparison_table(text):
    """
    Format the comparison text into an HTML table structure
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
            
            # Split content into contract1 and contract2 parts
            parts = re.split(r'#### (Contract 1|Contract 2)(?:\n|$)', content)
            
            if len(parts) > 2:  # We have proper split between contracts
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

def compare_contracts_with_claude(contract1_text, contract2_text, analysis_focus, custom_prompt):
    """Use Claude AI to compare contracts and generate insights."""
    
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    
    # Build context based on selected focus areas and custom instructions
    context = "As a procurement expert specialising in IT services for ERP projects, create a detailed side-by-side comparison of these contracts "
    
    # Add selected focus areas
    if analysis_focus:
        context += "specifically focusing on the following aspects: " + ", ".join(analysis_focus) + ". "
    
    # Add custom instructions
    if custom_prompt:
        context += custom_prompt
    
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
    """
    
    try:
        response = client.messages.create(
            model=st.secrets["ANTHROPIC_MODEL"],
            max_tokens=4000,
            temperature=0.2,
            system="You are an expert procurement analyst specialising in IT and ERP service contracts. Create a clear side-by-side comparison of contract terms, focused only on the specific topics requested. Format your response as a structured comparison with separate sections for each contract under each topic. Use bullet points and bold formatting for clarity and emphasis on key differences. Write in British English.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return response.content[0].text
    except Exception as e:
        return f"Error calling Claude API: {str(e)}"

def main():
    # App header
    st.markdown('<div class="title">ERP Contract Comparison Tool</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Side-by-Side Comparison Powered by Claude AI</div>', unsafe_allow_html=True)
    
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
        Results are presented in British English.
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
            with st.spinner("Creating side-by-side comparison... This may take a moment..."):
                contract1_text = extract_text(contract1_file)
                contract2_text = extract_text(contract2_file)
                
                # Default names if not provided
                if not contract1_name:
                    contract1_name = contract1_file.name
                if not contract2_name:
                    contract2_name = contract2_file.name
                
                # Generate the comparison
                analysis_result = compare_contracts_with_claude(
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
                    'result': analysis_result
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
            
            st.markdown(f'<div class="section-header">Side-by-Side Comparison</div>', unsafe_allow_html=True)
            
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
            
            # Process and display the comparison in a table format
            formatted_comparison = format_comparison_table(analysis['result'])
            st.markdown(formatted_comparison, unsafe_allow_html=True)
            
            # Download button for the comparison
            st.download_button(
                label="Download Comparison Report",
                data=f"# Side-by-Side Contract Comparison: {analysis['contract1_name']} vs {analysis['contract2_name']}\n\n" +
                     f"Analysis Date: {analysis['timestamp']}\n\n" +
                     f"Focus Areas: {', '.join(analysis['focus_areas']) if analysis['focus_areas'] else 'Custom analysis'}\n\n" +
                     analysis['result'],
                file_name=f"contract_comparison_{datetime.now().strftime('%Y%m%d')}.md",
                mime="text/markdown"
            )
        else:
            st.info("Upload contracts and select focus areas to generate a side-by-side comparison")
            
    # History Tab
    with tab3:
        st.markdown('<div class="section-header">Comparison History</div>', unsafe_allow_html=True)
        
        if st.session_state.analysis_history:
            for i, analysis in enumerate(reversed(st.session_state.analysis_history)):
                with st.expander(f"{analysis['contract1_name']} vs {analysis['contract2_name']} - {analysis['timestamp']}"):
                    # Show focus areas
                    focus_areas = "Areas: " + ", ".join(analysis['focus_areas']) if analysis['focus_areas'] else "Custom analysis"
                    st.markdown(f"**{focus_areas}**")
                    
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
