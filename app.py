from flask import Flask, request, jsonify, render_template
import re
from collections import Counter
import nltk
from nltk.corpus import words, brown
import string

# Initialize Flask app
app = Flask(__name__)

# Download necessary NLTK resources
nltk.download('words')
nltk.download('brown')

class AutoCorrect:
    def __init__(self):
        # Create word frequency dictionary from corpus
        self.word_counts = Counter()
        
        # Add words from NLTK corpus
        self.word_counts.update(w.lower() for w in words.words())
        self.word_counts.update(w.lower() for w in brown.words())
        
        # Common typing errors and corrections
        self.common_errors = {
            'teh': 'the', 'recieve': 'receive', 'wierd': 'weird',
            'accomodate': 'accommodate', 'occured': 'occurred',
            'definately': 'definitely', 'seperate': 'separate',
            'untill': 'until', 'wich': 'which', 'reccommend': 'recommend'
        }
        
        # Homophones with context examples
        self.homophones = {
            'their': ['their house', 'their car', 'their opinion'],
            'there': ['over there', 'there is', 'there are'],
            'they\'re': ['they\'re going', 'they\'re happy', 'they\'re late'],
            'your': ['your book', 'your car', 'your turn'],
            'you\'re': ['you\'re right', 'you\'re welcome', 'you\'re late'],
            'its': ['its color', 'its shape', 'its owner'],
            'it\'s': ['it\'s time', 'it\'s raining', 'it\'s cold']
        }
        
        # User custom dictionary for personalization
        self.user_dictionary = {}
        
    def tokenize(self, text):
        """Split text into words, keeping punctuation separate."""
        return re.findall(r'\b\w+\b|\S', text.lower())
    
    def known(self, words):
        """Return the subset of words that appear in the dictionary."""
        return {w for w in words if w in self.word_counts or w in self.user_dictionary}
    
    def edit_distance_1(self, word):
        """Return all strings that are one edit away from word."""
        letters = string.ascii_lowercase
        splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
        
        # Deletions
        deletes = [L + R[1:] for L, R in splits if R]
        
        # Transpositions
        transposes = [L + R[1] + R[0] + R[2:] for L, R in splits if len(R) > 1]
        
        # Replacements
        replaces = [L + c + R[1:] for L, R in splits if R for c in letters]
        
        # Insertions
        inserts = [L + c + R for L, R in splits for c in letters]
        
        return set(deletes + transposes + replaces + inserts)
    
    def edit_distance_2(self, word):
        """Return all strings that are two edits away from word."""
        return {e2 for e1 in self.edit_distance_1(word) for e2 in self.edit_distance_1(e1)}
    
    def get_candidates(self, word):
        """Get possible spelling corrections for word."""
        # Check common errors dictionary first
        if word in self.common_errors:
            return [self.common_errors[word]]
            
        # Check if word is already correct or in user dictionary
        if word in self.word_counts or word in self.user_dictionary:
            return [word]
        
        # Check words with edit distance 1
        candidates1 = self.known(self.edit_distance_1(word))
        if candidates1:
            return sorted(candidates1, key=lambda x: self.word_counts.get(x, 0), reverse=True)
        
        # Check words with edit distance 2
        candidates2 = self.known(self.edit_distance_2(word))
        if candidates2:
            return sorted(candidates2, key=lambda x: self.word_counts.get(x, 0), reverse=True)
        
        # If no candidates found, return the original word
        return [word]
    
    def check_homophone_context(self, text, word, position):
        """Check if a word might be a homophone mistake based on context."""
        words = text.split()
        if position >= len(words):
            return None
            
        current_word = words[position].lower().strip(string.punctuation)
        
        # Check if word is a homophone
        for correct, contexts in self.homophones.items():
            if current_word == correct.lower():
                continue  # Word is already correct
                
            # Check if word might be confused with this homophone
            for other_homophone in self.homophones:
                if other_homophone == correct:
                    continue
                    
                if current_word == other_homophone.lower():
                    # Get surrounding context (3 words before and after)
                    start = max(0, position - 3)
                    end = min(len(words), position + 4)
                    context = ' '.join(words[start:end]).lower()
                    
                    # Check if the correct context patterns appear
                    for pattern in contexts:
                        if any(part.lower() in context for part in pattern.split()):
                            return correct
        
        return None
    
    def correct_text(self, text):
        """Correct the entire text."""
        tokens = self.tokenize(text)
        corrected = []
        
        for i, token in enumerate(tokens):
            # Skip punctuation
            if token in string.punctuation or len(token) == 0:
                corrected.append(token)
                continue
                
            # Check for homophone errors
            homophone_correction = self.check_homophone_context(text, token, i)
            if homophone_correction:
                corrected.append(homophone_correction)
                continue
                
            # Get correction candidates
            candidates = self.get_candidates(token)
            corrected.append(candidates[0])  # Use the most likely correction
            
        # Reconstruct text with proper spacing
        result = ""
        for i, token in enumerate(corrected):
            if token in string.punctuation:
                result = result.rstrip() + token + " "
            elif i > 0 and corrected[i-1] in '.!?':
                result += token.capitalize() + " "
            else:
                result += token + " "
                
        return result.strip()
    
    def add_to_user_dictionary(self, word):
        """Add a word to the user's custom dictionary."""
        self.user_dictionary[word.lower()] = True
        return {"success": True, "message": f"Added '{word}' to your custom dictionary"}
        
    def get_suggestions(self, word, limit=5):
        """Get spelling suggestions for a single word."""
        candidates = self.get_candidates(word)
        return candidates[:limit]

# Initialize the autocorrect system
autocorrect = AutoCorrect()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/correct', methods=['POST'])
def correct():
    data = request.get_json()
    text = data.get('text', '')
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
        
    corrected_text = autocorrect.correct_text(text)
    
    return jsonify({
        "original": text,
        "corrected": corrected_text
    })

@app.route('/api/suggest', methods=['POST'])
def suggest():
    data = request.get_json()
    word = data.get('word', '')
    
    if not word:
        return jsonify({"error": "No word provided"}), 400
        
    suggestions = autocorrect.get_suggestions(word)
    
    return jsonify({
        "word": word,
        "suggestions": suggestions
    })

@app.route('/api/add-to-dictionary', methods=['POST'])
def add_to_dictionary():
    data = request.get_json()
    word = data.get('word', '')
    
    if not word:
        return jsonify({"error": "No word provided"}), 400
        
    result = autocorrect.add_to_user_dictionary(word)
    
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)