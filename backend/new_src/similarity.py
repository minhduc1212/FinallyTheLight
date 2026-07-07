"""
similarity.py - TF-IDF based cosine similarity calculations for duplicate and lazy translation checks.
"""
import re
import math
import collections

def calculate_tfidf_cosine_similarity(text1: str, text2: str) -> float:
    """Calculates TF-IDF Weighted Cosine Similarity between two texts in pure Python."""
    words1 = re.findall(r'\w+', text1.lower())
    words2 = re.findall(r'\w+', text2.lower())
    
    # Use Trigrams (3-grams) to capture phrase structure, 
    # crucial for preventing false-positives in monosyllabic languages like Vietnamese/Chinese
    b1 = list(zip(words1, words1[1:], words1[2:]))
    b2 = list(zip(words2, words2[1:], words2[2:]))
    
    if not b1 or not b2:
        return 0.0
        
    c1 = collections.Counter(b1)
    c2 = collections.Counter(b2)
    
    all_words = set(c1.keys()).union(set(c2.keys()))
    
    idf = {}
    for word in all_words:
        df = 0
        if word in c1:
            df += 1
        if word in c2:
            df += 1
        idf[word] = math.log(2.0 / df) + 1.0
        
    vec1 = {word: c1[word] * idf[word] for word in c1}
    vec2 = {word: c2[word] * idf[word] for word in c2}
    
    dot_product = sum(vec1[w] * vec2[w] for w in vec1 if w in vec2)
    norm_a = sum(v * v for v in vec1.values())
    norm_b = sum(v * v for v in vec2.values())
    
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
        
    return dot_product / (math.sqrt(norm_a) * math.sqrt(norm_b))
