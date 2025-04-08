import os
import sys
import mammoth
import re

def convert_docx_to_md(docx_path, md_path=None):
    """
    Konvertuje DOCX dokument u Markdown format koristeći mammoth biblioteku.
    
    Args:
        docx_path (str): Putanja do DOCX fajla
        md_path (str, optional): Putanja gde će biti sačuvan MD fajl. Ako nije navedeno,
                                 koristiće se isto ime kao DOCX fajl, samo sa .md ekstenzijom
    
    Returns:
        str: Putanja do kreiranog MD fajla
    """
    if not os.path.exists(docx_path):
        raise FileNotFoundError(f"DOCX fajl nije pronađen: {docx_path}")
    
    # Ako nije navedena putanja za MD fajl, kreiraj je na osnovu DOCX putanje
    if md_path is None:
        md_path = os.path.splitext(docx_path)[0] + ".md"
    
    try:
        # Konvertuj DOCX u HTML
        with open(docx_path, "rb") as docx_file:
            result = mammoth.convert_to_html(docx_file)
            html = result.value
        
        # Konvertuj HTML u Markdown
        md_content = html_to_markdown(html)
        
        # Obradi numerisane naslove
        md_content = process_numbered_headings(md_content)
        
        # Sačuvaj Markdown u fajl
        with open(md_path, "w", encoding="utf-8") as md_file:
            md_file.write(md_content)
        
        print(f"Konverzija uspešno završena. MD fajl sačuvan na: {md_path}")
        return md_path
    
    except Exception as e:
        print(f"Greška prilikom konverzije: {e}")
        raise

def html_to_markdown(html):
    """
    Konvertuje HTML u Markdown format.
    
    Args:
        html (str): HTML sadržaj
    
    Returns:
        str: Markdown sadržaj
    """
    # Zameni HTML tagove sa Markdown ekvivalentima
    # Naslovi
    html = re.sub(r'<h1>(.*?)</h1>', r'# \1\n\n', html)
    html = re.sub(r'<h2>(.*?)</h2>', r'## \1\n\n', html)
    html = re.sub(r'<h3>(.*?)</h3>', r'### \1\n\n', html)
    html = re.sub(r'<h4>(.*?)</h4>', r'#### \1\n\n', html)
    html = re.sub(r'<h5>(.*?)</h5>', r'##### \1\n\n', html)
    html = re.sub(r'<h6>(.*?)</h6>', r'###### \1\n\n', html)
    
    # Paragrafi
    html = re.sub(r'<p>(.*?)</p>', r'\1\n\n', html)
    
    # Bold i italic
    html = re.sub(r'<strong>(.*?)</strong>', r'**\1**', html)
    html = re.sub(r'<em>(.*?)</em>', r'*\1*', html)
    
    # Linkovi
    html = re.sub(r'<a href="(.*?)">(.*?)</a>', r'[\2](\1)', html)
    
    # Liste
    html = re.sub(r'<ul>(.*?)</ul>', lambda m: process_list(m.group(1), '*'), html, flags=re.DOTALL)
    html = re.sub(r'<ol>(.*?)</ol>', lambda m: process_list(m.group(1), '1.'), html, flags=re.DOTALL)
    
    # Tabele
    html = re.sub(r'<table>(.*?)</table>', process_table, html, flags=re.DOTALL)
    
    # Čišćenje preostalih HTML tagova
    html = re.sub(r'<.*?>', '', html)
    
    # Čišćenje višestrukih novih redova
    html = re.sub(r'\n{3,}', '\n\n', html)
    
    return html

def process_numbered_headings(md_content):
    """
    Obradi numerisane naslove u Markdown sadržaju.
    
    Args:
        md_content (str): Markdown sadržaj
    
    Returns:
        str: Markdown sadržaj sa obrađenim numerisanim naslovima
    """
    # Traži naslove u sadržaju
    heading_pattern = r'^(#+) (.*?)$'
    
    lines = md_content.split('\n')
    processed_lines = []
    
    # Traži linkove u sadržaju za identifikaciju numerisanih poglavlja
    toc_links = {}
    for line in lines:
        toc_match = re.search(r'\[\*\*(\d+\.\d+(?:\.\d+)*)\*\*\s+\*\*(.*?)\*\*\s+(\d+)\]\(#(.*?)\)', line)
        if toc_match:
            chapter_num = toc_match.group(1)
            chapter_title = toc_match.group(2).strip()
            toc_links[chapter_title.lower()] = chapter_num
    
    # Obradi naslove
    for line in lines:
        heading_match = re.search(heading_pattern, line, re.MULTILINE)
        if heading_match:
            level = len(heading_match.group(1))  # Broj # oznaka
            title = heading_match.group(2).strip()
            
            # Proveri da li je naslov u sadržaju
            for toc_title, chapter_num in toc_links.items():
                # Proveri da li se naslov poklapa sa naslovom iz sadržaja (ignoriši case)
                if title.lower() in toc_title or toc_title in title.lower():
                    # Dodaj numeraciju poglavlja
                    line = f"{'#' * level} {chapter_num} {title}"
                    break
        
        processed_lines.append(line)
    
    return '\n'.join(processed_lines)

def process_list(list_content, marker):
    """
    Procesira HTML listu i konvertuje je u Markdown format.
    
    Args:
        list_content (str): Sadržaj HTML liste
        marker (str): Marker za listu (* za neuređenu, 1. za uređenu)
    
    Returns:
        str: Markdown lista
    """
    items = re.findall(r'<li>(.*?)</li>', list_content, re.DOTALL)
    md_list = '\n'
    for item in items:
        md_list += f"{marker} {item.strip()}\n"
    return md_list + '\n'

def process_table(match):
    """
    Procesira HTML tabelu i konvertuje je u Markdown format.
    
    Args:
        match: Rezultat regex pretrage koji sadrži HTML tabelu
    
    Returns:
        str: Markdown tabela
    """
    table_content = match.group(1)
    
    # Izdvoji redove tabele
    rows = re.findall(r'<tr>(.*?)</tr>', table_content, re.DOTALL)
    if not rows:
        return ''
    
    md_table = '\n'
    
    # Procesiranje zaglavlja tabele
    header_cells = re.findall(r'<th>(.*?)</th>', rows[0], re.DOTALL)
    if not header_cells:
        header_cells = re.findall(r'<td>(.*?)</td>', rows[0], re.DOTALL)
    
    if header_cells:
        md_table += '|'
        for cell in header_cells:
            md_table += f" {cell.strip()} |"
        md_table += '\n|'
        
        # Dodaj separator
        for _ in range(len(header_cells)):
            md_table += ' --- |'
        md_table += '\n'
    
    # Procesiranje redova tabele
    start_idx = 1 if header_cells else 0
    for row in rows[start_idx:]:
        cells = re.findall(r'<td>(.*?)</td>', row, re.DOTALL)
        if cells:
            md_table += '|'
            for cell in cells:
                md_table += f" {cell.strip()} |"
            md_table += '\n'
    
    return md_table + '\n'

def main():
    """
    Glavna funkcija za pokretanje konverzije iz komandne linije.
    
    Upotreba:
        python docx_to_md_mammoth.py putanja/do/dokumenta.docx [putanja/do/izlaza.md]
    """
    if len(sys.argv) < 2:
        print("Greška: Nedostaje putanja do DOCX fajla.")
        print("Upotreba: python docx_to_md_mammoth.py putanja/do/dokumenta.docx [putanja/do/izlaza.md]")
        return 1
    
    docx_path = sys.argv[1]
    md_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        convert_docx_to_md(docx_path, md_path)
        return 0
    except Exception as e:
        print(f"Greška prilikom konverzije: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
