import streamlit as st
import re
import requests
from io import StringIO

st.set_page_config(page_title="BED File Creator", layout="wide")

st.title("Genomic Coordinates to BED File Converter")
st.markdown("Convert genomic positions to BED format with optional hg19 and hg38 conversion")

# Sidebar for options
st.sidebar.header("Settings")
input_assembly = st.sidebar.selectbox("Input Assembly", ["hg19", "hg38"], index=0)
output_assembly = st.sidebar.selectbox("Output Assembly", ["hg19", "hg38"], index=1)
perform_liftover = st.sidebar.checkbox("Perform LiftOver", value=(input_assembly != output_assembly))

st.sidebar.markdown("---")
st.sidebar.markdown("### Input Format Examples")
st.sidebar.code("chr1:1000000\nchr2:5000000-5001000\n3:1234567-1234890")

def parse_position(line):
    """Parse a genomic position string into chr, start, end"""
    line = line.strip()
    if not line:
        return None
    
    # Add 'chr' prefix if missing
    if not line.startswith('chr'):
        line = 'chr' + line
    
    # Pattern for chr:start or chr:start-end
    pattern1 = r'(chr[\dXYM]+):(\d+)-(\d+)'
    pattern2 = r'(chr[\dXYM]+):(\d+)'
    
    match = re.match(pattern1, line)
    if match:
        chrom, start, end = match.groups()
        return (chrom, int(start), int(end))
    
    match = re.match(pattern2, line)
    if match:
        chrom, pos = match.groups()
        pos = int(pos)
        return (chrom, pos, pos + 1)
    
    return None

def liftover_pyliftover(chrom, start, end, from_assembly, to_assembly):
    """Use alternative liftover method via Ensembl API"""
    try:
        # Ensembl REST API for coordinate mapping
        server = "https://rest.ensembl.org"
        
        # Map assembly names
        assembly_map = {
            "hg19": "GRCh37",
            "hg38": "GRCh38"
        }
        
        from_asm = assembly_map.get(from_assembly, from_assembly)
        to_asm = assembly_map.get(to_assembly, to_assembly)
        
        # Remove 'chr' prefix for Ensembl
        chrom_clean = chrom.replace('chr', '')
        
        ext = f"/map/human/{from_asm}/{chrom_clean}:{start}..{end}/{to_asm}?"
        
        response = requests.get(server + ext, 
                              headers={"Content-Type": "application/json"},
                              timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if "mappings" in data and len(data["mappings"]) > 0:
                mapped = data["mappings"][0]["mapped"]
                # Add chr prefix back
                new_chrom = "chr" + mapped["seq_region_name"]
                new_start = mapped["start"]
                new_end = mapped["end"]
                return (new_chrom, new_start, new_end)
        
        return None
    except Exception as e:
        st.error(f"LiftOver error: {str(e)}")
        return None

# Main input area
st.markdown("### Enter Genomic Positions")
st.markdown("**One position per line.** Formats: `chr1:1000000` or `chr1:1000000-1001000`")

input_text = st.text_area(
    "Paste your positions here:",
    height=200,
    placeholder="chr1:1000000\nchr2:5000000-5001000\nchr3:1234567"
)

if st.button("Convert to BED", type="primary"):
    if not input_text.strip():
        st.warning("Please enter some genomic positions.")
    else:
        lines = input_text.strip().split('\n')
        bed_entries = []
        failed_lines = []
        liftover_failed = []
        
        with st.spinner("Processing coordinates..."):
            for idx, line in enumerate(lines, 1):
                parsed = parse_position(line)
                
                if parsed is None:
                    failed_lines.append(f"Line {idx}: {line}")
                    continue
                
                chrom, start, end = parsed
                
                # Perform liftover if requested
                if perform_liftover and input_assembly != output_assembly:
                    lifted = liftover_pyliftover(chrom, start, end, input_assembly, output_assembly)
                    if lifted:
                        chrom, start, end = lifted
                    else:
                        liftover_failed.append(f"Line {idx}: {line} ({chrom}:{start}-{end})")
                        continue
                
                bed_entries.append(f"{chrom}\t{start}\t{end}")
        
        # Display results
        if bed_entries:
            st.success(f"Successfully converted {len(bed_entries)} position(s)")
            
            bed_output = '\n'.join(bed_entries)
            
            st.markdown("### BED File Output")
            st.code(bed_output, language="text")
            
            # Download button
            st.download_button(
                label="Download BED File",
                data=bed_output,
                file_name=f"coordinates_{output_assembly}.bed",
                mime="text/plain"
            )
        
        # Show errors if any
        if failed_lines:
            st.error(f"Failed to parse {len(failed_lines)} line(s):")
            for line in failed_lines:
                st.text(line)
        
        if liftover_failed:
            st.warning(f"LiftOver failed for {len(liftover_failed)} position(s):")
            for line in liftover_failed:
                st.text(line)

# Information section
with st.expander("About BED Format"):
    st.markdown("""
    **BED (Browser Extensible Data)** format is a tab-delimited text format for genomic intervals.
    
    The basic 3-column format includes:
    - **Column 1**: Chromosome (e.g., chr1)
    - **Column 2**: Start position (0-based)
    - **Column 3**: End position (1-based, exclusive)
    
    **LiftOver** converts coordinates between genome assemblies (hg19 and hg38).
    
    Note: This tool uses the Ensembl REST API for liftOver conversions.
    """)

st.markdown("---")
st.markdown("*Built with Streamlit*")
