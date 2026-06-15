"""
MirageProxy — PII/sensitive data scrambling layer (The Mirage Protocol) for cloud LLM interactions.

Detects PII/sensitive fields in outbound text, replaces with semantically-consistent
synthetic equivalents, and reverses the mapping on inbound responses.
"""

from dataclasses import dataclass, field
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)


class PIIType(Enum):
    """Types of personally identifiable information and sensitive fields."""
    PERSON = "person"           # Names
    EMAIL = "email"             # Email addresses
    PHONE = "phone"             # Phone numbers
    SSN = "ssn"                 # Social security numbers
    CREDIT_CARD = "credit_card" # Credit card numbers
    ADDRESS = "address"         # Physical addresses
    PASSWORD = "password"       # Passwords and secrets
    MEDICAL = "medical"         # Health/medical information
    FINANCIAL = "financial"     # Financial data (account numbers, balances)
    GOSSIP = "gossip"           # Personal gossip about third parties
    LOCATION = "location"       # Specific personal locations
    DATE_OF_BIRTH = "dob"       # Birthdates
    CUSTOM_SECRET = "secret"    # User-marked secrets
    AADHAR = "aadhar"           # Aadhaar card numbers
    PASSPORT = "passport"       # Passport numbers


@dataclass
class PIIFinding:
    """A single detected PII occurrence."""
    pii_type: PIIType
    original: str
    start: int
    end: int
    confidence: float = 1.0


@dataclass
class MirageMap:
    """Reversible mapping from original sensitive data to synthetic replacements."""
    forward: dict[str, str] = field(default_factory=dict)   # original → fake
    reverse: dict[str, str] = field(default_factory=dict)   # fake → original
    
    def add(self, original: str, synthetic: str):
        self.forward[original] = synthetic
        self.reverse[synthetic] = original


class PIIDetector:
    """
    Multi-strategy PII and sensitive data detection.
    
    Strategy (tiered, fast-to-slow):
    1. Regex patterns — SSN, credit card, email, phone, Aadhaar, Passport (instant)
    2. Keyword triggers — passwords, secrets, medical terms, Aadhaar, Passport (instant)
    3. NER model — names, addresses, organizations (local, ~50ms)
    
    The NER model is optional. Without it, detection still works
    via regex + keywords, just with lower recall for unstructured PII
    like names embedded in natural language.
    """
    
    # Regex patterns (high precision)
    PATTERNS: dict[PIIType, list[str]] = {
        PIIType.SSN: [r'\b\d{3}-\d{2}-\d{4}\b'],
        PIIType.CREDIT_CARD: [r'\b(?:\d{4}[-\s]?){3}\d{4}\b'],
        PIIType.EMAIL: [r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'],
        PIIType.PHONE: [
            r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',
            r'\+\d{1,3}[-.\s]?\d{3,14}\b',
        ],
        PIIType.DATE_OF_BIRTH: [
            r'\b(?:born|birthday|dob|date of birth)\s*:?\s*\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b',
        ],
        PIIType.AADHAR: [
            r'\b\d{4}\s\d{4}\s\d{4}\b',  # Spaced format: XXXX XXXX XXXX
            r'\b\d{12}\b',              # Plain 12-digit format
        ],
        PIIType.PASSPORT: [
            r'\b[A-Z][0-9]{7}\b',        # e.g., Indian Passport (1 letter, 7 digits)
        ],
    }
    
    # Keyword triggers (medium precision — context-dependent)
    KEYWORD_TRIGGERS: dict[PIIType, list[str]] = {
        PIIType.PASSWORD: [
            "password", "passwd", "passcode", "pin code", "secret key",
            "api key", "api_key", "token", "credential", "private key",
        ],
        PIIType.MEDICAL: [
            "blood pressure", "diagnosis", "prescription", "medication",
            "symptoms", "blood test", "cholesterol", "heart rate",
            "therapy session", "mental health", "anxiety", "depression",
            "blood sugar", "insulin", "allergies", "surgery",
        ],
        PIIType.FINANCIAL: [
            "bank account", "routing number", "account number",
            "credit score", "salary", "income", "tax return",
            "investment", "mortgage", "loan balance",
        ],
        PIIType.GOSSIP: [
            "don't tell", "between us", "secret about", "heard that",
            "apparently they", "cheating", "affair", "divorce",
            "fired from", "got arrested", "in trouble",
            "don't mention", "keep this quiet", "off the record",
        ],
    }
    
    def __init__(self):
        self._ner_model = None
    
    def scan(self, text: str) -> list[PIIFinding]:
        """Scan text for all PII occurrences."""
        findings = []
        
        # 1. Regex patterns
        for pii_type, patterns in self.PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    findings.append(PIIFinding(
                        pii_type=pii_type,
                        original=match.group(),
                        start=match.start(),
                        end=match.end(),
                    ))
        
        # 2. Keyword triggers
        text_lower = text.lower()
        for pii_type, keywords in self.KEYWORD_TRIGGERS.items():
            for kw in keywords:
                if kw in text_lower:
                    # Find the sentence containing the keyword
                    idx = text_lower.index(kw)
                    findings.append(PIIFinding(
                        pii_type=pii_type,
                        original=kw,
                        start=idx,
                        end=idx + len(kw),
                        confidence=0.7,  # Lower confidence for keyword-only
                    ))
        
        # 3. NER model (optional, loaded lazily)
        ner_findings = self._run_ner(text)
        findings.extend(ner_findings)
        
        return findings
    
    def _run_ner(self, text: str) -> list[PIIFinding]:
        """Run NER model for name/address/org detection. Optional."""
        try:
            if self._ner_model is None:
                self._ner_model = self._load_ner_model()
            if self._ner_model is None:
                return []
            
            # Use the model to find entities
            entities = self._ner_model(text)
            findings = []
            for ent in entities:
                pii_type = self._ner_label_to_pii(ent.get("entity_group", ""))
                if pii_type:
                    findings.append(PIIFinding(
                        pii_type=pii_type,
                        original=ent["word"],
                        start=ent["start"],
                        end=ent["end"],
                        confidence=ent.get("score", 0.5),
                    ))
            return findings
        except Exception as e:
            logger.debug(f"[PIIDetector] NER unavailable: {e}")
            return []
    
    def _load_ner_model(self):
        """Try to load a local NER model. Returns None if unavailable."""
        try:
            from transformers import pipeline
            return pipeline(
                "ner",
                model="dslim/bert-base-NER",
                aggregation_strategy="simple",
                device=-1,  # CPU
            )
        except ImportError:
            logger.info("[PIIDetector] transformers not installed, NER disabled")
            return None
    
    def _ner_label_to_pii(self, label: str) -> PIIType | None:
        """Map NER labels to PIIType."""
        mapping = {
            "PER": PIIType.PERSON,
            "LOC": PIIType.LOCATION,
            "ORG": PIIType.PERSON,  # Treat orgs as personal context
        }
        return mapping.get(label)


class ScrambleEngine:
    """
    Generates semantically-consistent synthetic replacements for PII (Mirage Protocol).
    
    "Dr. Amara Singh" → "Dr. Elena Novak" (not "[REDACTED]")
    "555-123-4567"    → "555-987-6543"    (not "XXX-XXX-XXXX")
    
    This preserves LLM reasoning quality — the model can still
    understand relationships and context, just with fake identifiers.
    """
    
    # Synthetic name pools (diverse, realistic)
    FAKE_FIRST_NAMES = [
        "Elena", "Marcus", "Priya", "Chen", "Sofia", "Omar",
        "Yuki", "André", "Fatima", "Liam", "Amira", "Dmitri",
        "Zara", "Kenji", "Nadia", "Ravi", "Clara", "Tomas",
    ]
    FAKE_LAST_NAMES = [
        "Novak", "Okonkwo", "Petrov", "Tanaka", "Rivera", "Johansson",
        "Dubois", "Kapoor", "Nkomo", "Bergström", "Castillo", "Nguyen",
    ]
    FAKE_DOMAINS = ["example.com", "sample.org", "test.net"]
    
    def __init__(self):
        self._name_counter = 0
        self._phone_counter = 0
    
    def scramble(self, text: str, findings: list[PIIFinding], smap: MirageMap | None = None) -> tuple[str, MirageMap]:
        """
        Replace all PII in text with synthetic equivalents.
        Returns scrambled text and the reversible mapping.
        """
        if smap is None:
            smap = MirageMap()
        
        # Sort findings by position (reverse order for safe replacement)
        sorted_findings = sorted(findings, key=lambda f: f.start, reverse=True)
        
        result = text
        for finding in sorted_findings:
            if finding.original in smap.forward:
                # Already have a replacement for this exact string
                synthetic = smap.forward[finding.original]
            else:
                synthetic = self._generate_synthetic(finding)
                smap.add(finding.original, synthetic)
            
            result = result[:finding.start] + synthetic + result[finding.end:]
        
        return result, smap
    
    def _generate_synthetic(self, finding: PIIFinding) -> str:
        """Generate a type-appropriate synthetic replacement."""
        match finding.pii_type:
            case PIIType.PERSON:
                first = self.FAKE_FIRST_NAMES[self._name_counter % len(self.FAKE_FIRST_NAMES)]
                last = self.FAKE_LAST_NAMES[self._name_counter % len(self.FAKE_LAST_NAMES)]
                self._name_counter += 1
                # Preserve titles (Dr., Mr., etc.)
                original = finding.original
                for title in ["Dr. ", "Mr. ", "Mrs. ", "Ms. ", "Prof. "]:
                    if original.startswith(title):
                        return f"{title}{first} {last}"
                return f"{first} {last}"
            
            case PIIType.EMAIL:
                idx = self._name_counter % len(self.FAKE_FIRST_NAMES)
                domain = self.FAKE_DOMAINS[idx % len(self.FAKE_DOMAINS)]
                return f"{self.FAKE_FIRST_NAMES[idx].lower()}@{domain}"
            
            case PIIType.PHONE:
                self._phone_counter += 1
                return f"555-{100 + self._phone_counter:03d}-{1000 + self._phone_counter:04d}"
            
            case PIIType.SSN:
                return "XXX-XX-XXXX"  # Never generate a real SSN
            
            case PIIType.CREDIT_CARD:
                return "XXXX-XXXX-XXXX-XXXX"
            
            case PIIType.PASSWORD | PIIType.CUSTOM_SECRET:
                return "[REDACTED_SECRET]"
            
            case PIIType.AADHAR:
                return "XXXX XXXX XXXX"
            
            case PIIType.PASSPORT:
                return "X0000000"
            
            case PIIType.MEDICAL:
                # Keep the keyword but genericize the context
                return finding.original  # Medical keywords flag the level, not replaced
            
            case PIIType.GOSSIP:
                return finding.original  # Gossip keywords flag the level, not replaced
            
            case _:
                return f"[REDACTED_{finding.pii_type.value.upper()}]"


class RehydrateEngine:
    """Reverses synthetic replacements in LLM responses."""
    
    def rehydrate(self, text: str, smap: MirageMap) -> str:
        """Replace all synthetic tokens back to originals."""
        result = text
        # Sort by length (longest first) to avoid partial replacements
        for synthetic, original in sorted(
            smap.reverse.items(), key=lambda x: len(x[0]), reverse=True
        ):
            result = result.replace(synthetic, original)
        return result


class MirageProxy:
    """
    High-level proxy for cloud LLM interactions implementing the Mirage Protocol.
    
    Usage:
        proxy = MirageProxy()
        scrambled_prompt, session = proxy.scramble(user_prompt)
        # ... send scrambled_prompt to cloud LLM ...
        clean_response = proxy.rehydrate(llm_response, session)
    """
    
    def __init__(self):
        self.detector = PIIDetector()
        self.scrambler = ScrambleEngine()
        self.rehydrator = RehydrateEngine()
    
    def scramble(self, text: str, smap: MirageMap | None = None) -> tuple[str, MirageMap | None]:
        """
        Scan and scramble text for cloud transmission.
        
        Returns:
            (scrambled_text, map) if sensitive data/PII was found
            (original_text, None) if text is clean (unless smap is provided)
        """
        findings = self.detector.scan(text)
        if not findings and smap is None:
            logger.debug("[MirageProxy] No sensitive data detected, passing through")
            return text, None
        
        if findings:
            logger.info(
                f"[MirageProxy] Detected {len(findings)} sensitive items: "
                f"{[f.pii_type.value for f in findings]}"
            )
        scrambled, smap = self.scrambler.scramble(text, findings, smap)
        return scrambled, smap
    
    def rehydrate(self, text: str, smap: MirageMap | None) -> str:
        """Reverse scrambling on LLM response."""
        if smap is None:
            return text
        return self.rehydrator.rehydrate(text, smap)
