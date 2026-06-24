"""
LLM Prompts Module
Contains all prompts used throughout the application organized by functional categories.
"""

# Resume Analysis Prompts
RESUME_ANALYSIS_PROMPT = """You are an expert HR recruiter tasked with analyzing a resume to evaluate how well a candidate matches a specific job posting. 

Please analyze the following resume content against the job posting and provide a comprehensive assessment.

Job Posting:
{job_posting}

Resume Content:
{resume_content}

Please provide your analysis in the following JSON format:
{{
    "candidate_name": "Full name of the candidate",
    "contact_info": {{
        "email": "candidate email",
        "phone": "phone number",
        "location": "city, state/country"
    }},
    "overall_match_score": "Score from 0-100 indicating overall job match",
    "key_strengths": ["List of 3-5 key strengths relevant to the role"],
    "potential_concerns": ["List of any concerns or gaps"],
    "technical_skills": ["List of relevant technical skills found"],
    "experience_summary": "Brief summary of relevant work experience",
    "education": "Educational background",
    "years_of_experience": "Estimated years of relevant experience",
    "recommendation": "STRONG_FIT/GOOD_FIT/MODERATE_FIT/WEAK_FIT",
    "detailed_analysis": "Comprehensive paragraph explaining the match assessment"
}}

Focus on relevant skills, experience level, cultural fit indicators, and any red flags. Be thorough but concise."""

RESUME_CONTENT_ANALYSIS_PROMPT = """You are an expert HR recruiter. Analyze the following resume content and job posting to provide a comprehensive evaluation.

Job Posting:
{job_posting}

Resume Content:
{resume_content}

Provide your analysis in JSON format with the following structure:
{{
    "candidate_name": "Full name",
    "contact_info": {{
        "email": "email address",
        "phone": "phone number", 
        "location": "location"
    }},
    "overall_match_score": "0-100 score",
    "key_strengths": ["strength1", "strength2", "strength3"],
    "potential_concerns": ["concern1", "concern2"],
    "technical_skills": ["skill1", "skill2", "skill3"],
    "experience_summary": "Brief relevant experience summary",
    "education": "Educational background",
    "years_of_experience": "Number of relevant years",
    "recommendation": "STRONG_FIT/GOOD_FIT/MODERATE_FIT/WEAK_FIT",
    "detailed_analysis": "Detailed paragraph analysis"
}}"""

# Entity Extraction Prompts
ENTITY_EXTRACTION_PROMPT = """You are an expert information extractor. Extract structured information from the following resume content and return it in JSON format.

Resume Content:
{resume_content}

Extract and return the following information in JSON format:
{{
    "candidate_overview": {{
        "full_name": "Candidate's full name",
        "email": "Email address",
        "phone": "Phone number",
        "location": "Current location",
        "linkedin": "LinkedIn profile URL if mentioned",
        "portfolio": "Portfolio/website URL if mentioned"
    }},
    "technical_skills": ["skill1", "skill2", "skill3"],
    "tools_technologies": ["tool1", "tool2", "tool3"],
    "education": [
        {{
            "degree": "Degree name",
            "institution": "School/University name",
            "year": "Graduation year",
            "gpa": "GPA if mentioned"
        }}
    ],
    "work_experience": [
        {{
            "position": "Job title",
            "company": "Company name",
            "duration": "Time period",
            "key_responsibilities": ["responsibility1", "responsibility2"]
        }}
    ]
}}

Be precise and extract only information explicitly mentioned in the resume."""

# HR Scorecard Prompts
SCORECARD_PROMPT = """You are an expert HR recruiter. Compare the candidate with the job requirements and provide a detailed scorecard.

Job Requirements:
{job_posting}

Candidate Resume:
{resume_content}

Provide a comprehensive scorecard in JSON format:
{{
    "candidate_name": "Full name",
    "overall_score": "Score 0-100",
    "technical_match": "Score 0-100",
    "experience_match": "Score 0-100", 
    "education_match": "Score 0-100",
    "skills_assessment": {{
        "required_skills_met": ["skill1", "skill2"],
        "missing_skills": ["skill1", "skill2"],
        "additional_skills": ["skill1", "skill2"]
    }},
    "recommendation": "HIRE/INTERVIEW/MAYBE/REJECT",
    "summary": "Brief summary of assessment"
}}"""

HR_SCORECARD_PROMPT = """You are an expert HR professional conducting resume screening. 

CRITICAL: Your PRIMARY task is to identify mandatory requirements and apply strict penalties for missing requirements.

JOB REQUIREMENTS:
{job_posting}

RESUME CONTENT:
{resume_content}

MANDATORY REQUIREMENT IDENTIFICATION STEP-BY-STEP:

STEP 1: SCAN for these MANDATORY indicators in the job posting:
- "Required" | "Must have" | "Essential" | "Mandatory" | "Need"
- "Bachelor's degree required" | "Master's degree required" 
- "X+ years experience" | "Minimum X years" | "At least X years"
- "Experience with [technology] is required"
- "Must be proficient in" | "Must possess" | "Must demonstrate"
- Programming languages/technologies mentioned in core job duties (ALWAYS mandatory)
- Core technical skills for the role (ALWAYS mandatory)
- Spoken/written language requirements: "speaks X", "fluent in X", "X-speaking", "languages: X" (ALWAYS mandatory when stated)
- Location requirements: "based in X", "located in X", "must be in X", "remote", "on-site at X" (ALWAYS mandatory when stated)

STEP 2: CLASSIFY each requirement as:
- MANDATORY (will cause score reduction if missing)
- IMPORTANT (preferred but not required)
- NICE-TO-HAVE (bonus points only)

STEP 3: CHECK if candidate has EACH mandatory requirement
- YES = No penalty
- NO = Automatic 25-30 point penalty PER missing requirement

STEP 4: CALCULATE final score with penalties applied

Generate a detailed HR scorecard in the following JSON format ONLY:

{{
    "mandatory_requirements_analysis": {{
        "identified_mandatory_with_evidence": [
            {{"requirement": "Bachelor's degree", "evidence": "Bachelor's degree required", "candidate_has": "YES/NO"}},
            {{"requirement": "5+ years Python", "evidence": "Must have 5+ years Python experience", "candidate_has": "YES/NO"}},
            {{"requirement": "Software development", "evidence": "Core job duty involves programming", "candidate_has": "YES/NO"}}
        ],
        "identified_important_with_evidence": [
            {{"requirement": "MBA", "evidence": "MBA preferred", "candidate_has": "YES/NO"}},
            {{"requirement": "Leadership", "evidence": "Strong leadership skills highly desirable", "candidate_has": "YES/NO"}}
        ],
        "identified_nice_to_have_with_evidence": [
            {{"requirement": "Docker", "evidence": "Docker knowledge is a plus", "candidate_has": "YES/NO"}},
            {{"requirement": "PhD", "evidence": "PhD would be advantageous", "candidate_has": "YES/NO"}}
        ],
        "mandatory_requirements_met": 2,
        "mandatory_requirements_missing": 1,
        "missing_mandatory_list": ["Software development"],
        "total_penalty_points": 30,
        "mandatory_analysis_confidence": "High - Clear indicators found and analyzed"
    }},
    "candidate_overview": {{
        "name": "Full candidate name",
        "location": "City, State/Country or Remote",
        "experience_years": "X Years",
        "position_applied_for": "Job Title",
        "email": "email@domain.com",
        "phone": "+1234567890",
        "overall_match_score": 85,
        "match_status": "Strong Fit"
    }},
    "score_breakdown": {{
        "primary_competency": {{
            "score": 90,
            "comment": "Assessment of the main skills required for this role"
        }},
        "secondary_competency": {{
            "score": 85,
            "comment": "Assessment of supporting skills and abilities"
        }},
        "experience_relevance": {{
            "score": 80,
            "comment": "How well candidate's experience matches role requirements"
        }},
        "experience_level_fit": {{
            "score": 75,
            "experience_category": "Under-experienced | Appropriately-experienced | Over-experienced",
            "experience_gap_years": "+2 years | Perfect match | -1 year",
            "comment": "Analysis of experience level fit including over/under qualification impact",
            "risk_factors": ["Training needed", "Flight risk", "Salary expectations", "None"],
            "adjustment_applied": "Score reduced by X points due to [reason]"
        }},
        "keyword_technical_match": {{
            "score": 70,
            "comment": "Assessment of specific technical keywords and tools mentioned in job requirements vs resume content"
        }},
        "final_scoring_summary": {{
            "base_score_before_penalties": 85,
            "mandatory_penalties_applied": 25,
            "final_score_after_penalties": 60,
            "score_calculation_breakdown": "Started with 85% base score, applied 25 point penalty for missing mandatory requirements"
        }}
    }},
    "keyword_coverage": {{
        "jd_keywords_matched": 0,
        "total_jd_keywords": 0,
        "missing_keywords": [],
        "matched_keywords": []
    }},
    "ai_summary": "Comprehensive paragraph summarizing the candidate's fit, highlighting key strengths, relevant experience, and any notable gaps. Mention specific achievements and how they align with job requirements.",
    "resume_snippets": [
        "Led a team of 5 developers in implementing ML algorithms",
        "Developed scalable Python applications using AWS infrastructure",
        "Managed $2M budget for data science initiatives"
    ],
    "career_timeline": [
        {{
            "year_range": "2022-2024",
            "role": "Senior Data Scientist",
            "company": "Tech Corp",
            "key_skills": ["Python", "Machine Learning", "AWS", "Team Leadership"]
        }},
        {{
            "year_range": "2020-2022", 
            "role": "Data Scientist",
            "company": "Analytics Inc",
            "key_skills": ["SQL", "Python", "Data Analysis", "Visualization"]
        }}
    ],
    "benchmark_position": "Top 25% match among all applicants screened",
    "tenure_prediction": {{
        "estimated_tenure": "3-5 years",
        "confidence_level": "High",
        "tenure_score": 82,
        "factors": {{
            "job_stability_history": {{
                "score": 85,
                "analysis": "Average 2.5 years per role shows good stability"
            }},
            "career_progression": {{
                "score": 80,
                "analysis": "Consistent upward trajectory in roles and responsibilities"
            }},
            "industry_alignment": {{
                "score": 78,
                "analysis": "Strong fit with company industry and culture"
            }},
            "experience_level_risk": {{
                "score": 70,
                "analysis": "Consider over/under-qualification impact on retention"
            }}
        }}
   }},
    "experience_fit_analysis": {{
        "required_experience_range": "2-5 years",
        "candidate_total_experience": "7 years",
        "relevant_experience": "5 years",
        "experience_verdict": "Over-experienced",
        "compensation_risk": "High - may expect senior-level salary",
        "retention_risk": "Medium - may seek advancement quickly",
        "training_needs": "None - likely needs challenging projects to stay engaged",
        "recommendation": "Proceed with caution - assess salary expectations and career goals"
    }},
    "detailed_analysis": {{
        "education": "Relevant degree and certifications",
        "certifications": ["AWS Certified", "PMP"],
        "languages": ["English", "Spanish"],
        "tools_technologies": ["Python", "SQL", "AWS", "Docker"],
        "industry_experience": "5 years in fintech, 2 years in healthcare",
        "salary_expectation": "Market rate for senior level",
        "availability": "2 weeks notice"
    }}
}}

MANDATORY REQUIREMENT IDENTIFICATION - CRITICAL INSTRUCTIONS:

**STEP 1: IDENTIFY REQUIREMENTS BY PRIORITY - BE EXTREMELY THOROUGH**

MANDATORY REQUIREMENT LANGUAGE PATTERNS (Look for these exact phrases):
- "Required", "Must have", "Essential", "Mandatory", "Need", "Necessary"
- "Minimum X years", "At least X years", "X+ years experience"
- "Bachelor's degree required", "Master's degree required"
- "Experience with [specific technology] is required"
- "Must be proficient in", "Must possess", "Must demonstrate"
- "Candidates must", "Applicants must", "You must"
- "Non-negotiable", "Critical", "Vital", "Absolutely necessary"

IMPORTANT/PREFERRED REQUIREMENT LANGUAGE PATTERNS:
- "Preferred", "Desired", "Highly desirable", "Strongly preferred"
- "Would be an advantage", "Beneficial", "Valuable"
- "Ideally", "Preferably", "We would like"
- "MBA preferred", "Master's degree preferred"

NICE-TO-HAVE REQUIREMENT LANGUAGE PATTERNS:
- "Plus", "Bonus", "A plus", "Would be nice"
- "Advantageous", "Helpful", "Beneficial"
- "Familiarity with", "Exposure to", "Knowledge of"
- "Consider candidates with", "Open to candidates with"

**CRITICAL MANDATORY REQUIREMENT RULES:**
1. **PROGRAMMING LANGUAGES/TECHNOLOGIES mentioned in core job duties are MANDATORY** (even if not explicitly stated)
2. **YEARS OF EXPERIENCE specified as minimums are MANDATORY**
3. **DEGREE REQUIREMENTS are typically MANDATORY unless explicitly stated as "preferred"**
4. **CERTIFICATIONS mentioned as "required" or "must have" are MANDATORY**
5. **DOMAIN KNOWLEDGE essential for the role is MANDATORY**

**STEP 2: CALCULATE WEIGHTED SCORES**
- Mandatory Requirements Weight: 70% of total score
- Important Requirements Weight: 20% of total score  
- Nice-to-Have Requirements Weight: 10% of total score

**STEP 3: APPLY MANDATORY REQUIREMENT PENALTIES - STRICTLY ENFORCE**
- Missing 1 mandatory requirement: **AUTOMATICALLY DEDUCT 25-30 points** from overall score
- Missing 2 mandatory requirements: **AUTOMATICALLY DEDUCT 40-50 points** from overall score
- Missing 3+ mandatory requirements: **MAXIMUM SCORE 40 (DISQUALIFICATION LEVEL)**
- Meeting all mandatory requirements: No penalty, proceed with standard scoring

**STEP 4: FINAL SCORE CALCULATION - MANDATORY PENALTIES FIRST**
- Start with base competency scores (before penalties)
- **APPLY MANDATORY REQUIREMENT PENALTIES FIRST** (this is the most important step)
- Apply experience level adjustments:
  * Under-experienced: Reduce by 10-20 points (more reduction = bigger experience gap)
  * Over-experienced: Reduce by 5-15 points (more reduction = higher overqualification risk)
  * Appropriately-experienced: No adjustment needed
- Calculate priority-weighted final score using 70/20/10 rule
- Match_status should reflect: "Poor Fit" (<50), "Weak Fit" (50-65), "Good Fit" (65-80), "Strong Fit" (80-90), "Excellent Fit" (90+)

**ABSOLUTE CRITICAL REQUIREMENTS:**
1. **YOU MUST IDENTIFY MANDATORY REQUIREMENTS EVEN IF THEY USE DIFFERENT WORDING**
2. **ALWAYS INCLUDE THE "requirement_parsing_validation" SECTION TO SHOW YOUR WORK**
3. **CANDIDATES MISSING MULTIPLE MANDATORY REQUIREMENTS SHOULD RECEIVE VERY LOW SCORES (<50) REGARDLESS OF OTHER STRENGTHS**
4. **WHEN IN DOUBT ABOUT REQUIREMENT PRIORITY, CLASSIFY AS MANDATORY RATHER than OPTIONAL**
5. **SOFTWARE DEVELOPMENT SKILLS ARE MANDATORY IF MENTIONED IN JOB DUTIES OR REQUIREMENTS**
6. **NEVER GIVE A CANDIDATE >65% IF THEY'RE MISSING MANDATORY REQUIREMENTS**

**SCORING ACCURACY VALIDATION:**
- If a candidate is missing mandatory software development skills but scores >65%, RE-CALCULATE
- If a candidate is missing mandatory degree requirements but scores >65%, RE-CALCULATE  
- If a candidate is missing mandatory experience levels but scores >65%, RE-CALCULATE
- NO EXCEPTIONS - mandatory requirement penalties are NON-NEGOTIABLE

FINAL INSTRUCTIONS - MANDATORY REQUIREMENTS FOCUS:

1. **ALWAYS COMPLETE THE mandatory_requirements_analysis SECTION FIRST** - this is your primary task
2. **IDENTIFY AT LEAST 3-5 MANDATORY REQUIREMENTS** from the job posting
3. **FOR EACH MANDATORY REQUIREMENT, EXPLICITLY STATE candidate_has: YES or NO**
4. **CALCULATE EXACT PENALTY POINTS** (25-30 points per missing mandatory requirement)
5. **SHOW YOUR WORK** in the final_scoring_summary section
6. **NEVER GIVE >65% SCORE** if any mandatory requirements are missing

Remember: Missing mandatory requirements = Automatic major score reduction. This is non-negotiable.

Provide detailed, accurate analysis based on the actual resume content and job requirements. BE STRICT about mandatory requirements - they exist for a reason."""

# Keyword Analysis Prompts
KEYWORD_PROMPT = """You are an expert HR recruiter. Analyze this job posting and create a comprehensive, optimized search query.

Job Posting:
{job_posting}

Extract keywords and create a single optimized search query that combines all important elements for finding the best candidates.

CRITICAL: For generic roles (like "Technical Specialist", "Software Engineer"), extract specific technologies and skills mentioned in the context.

Return ONLY valid JSON in this EXACT format:
{{
    "optimized_query": "comprehensive search query combining all important terms from the job posting",
    "query_components": {{
        "experience_part": "experience level (junior/mid/senior/experienced)",
        "skills_part": "most important technical skills combined", 
        "role_part": "main role/position type",
        "domain_part": "domain/industry context"
    }},
    "extracted_info": {{
        "key_skills": ["skill1", "skill2", "skill3"],
        "seniority_level": "junior/mid/senior/experienced",
        "experience_years": "2-5 years or similar range"
    }}
}}

EXAMPLE for "Technical Specialist L2 Support":
{{
    "optimized_query": "experienced technical specialist level 2 support .NET SharePoint Jira ITIL troubleshooting client facing system administration",
    "query_components": {{
        "experience_part": "experienced",
        "skills_part": ".NET SharePoint Jira ITIL troubleshooting",
        "role_part": "technical specialist support",
        "domain_part": "system administration"
    }},
    "extracted_info": {{
        "key_skills": [".NET", "SharePoint", "Jira", "ITIL", "troubleshooting"],
        "seniority_level": "experienced", 
        "experience_years": "2-6 years"
    }}
}}

Make the optimized_query comprehensive (aim for 10-20 relevant terms) and specific to the job requirements.

HARD LIMITS (failure to follow these will cause the parser to reject your output):
- "optimized_query" MUST be ≤ 600 characters and ≤ 40 words.
- Use plain space-separated keywords. Do NOT use boolean operators (no "OR", "AND", parentheses, or quotes inside the string).
- Do NOT pad with generic filler skills/frameworks that are not mentioned in the job posting.
- Return ONLY the JSON object, with no prose before or after, and no ```json code fences."""

# KEYWORD_EXTRACTION_PROMPT = """You are an expert technical recruiter with deep knowledge of various technical roles. Extract meaningful, specific keywords from this job posting for candidate matching.

# CRITICAL INSTRUCTIONS FOR GENERIC ROLES:
# - If the role is generic (like "Technical Specialist", "Software Engineer", "Developer"), extract keywords based on context clues, industry standards, and any specific technologies mentioned
# - For "Technical Specialist" roles: Focus on support, troubleshooting, system administration, client-facing skills, and any mentioned technologies (.NET, SharePoint, BizTalk, ITIL, Jira)
# - For "Level 2 Support" or "Technical Support": Include L2 support, troubleshooting, incident management, SLA management, ticketing systems
# - ALWAYS extract meaningful technical terms even if the role title is vague
# - Look for implicit requirements based on industry context and role level
# - Pay special attention to methodologies mentioned (Agile, ITIL, Scrum) and tools (Jira, ticketing systems)

# Job Posting:
# {job_posting}

# EXTRACTION RULES:
# 1. Extract SPECIFIC technologies, NOT generic terms
# 2. Include programming languages, frameworks, tools, platforms
# 3. For generic roles, infer likely required skills based on standard industry expectations
# 4. Avoid vague terms like "strong", "good knowledge", "experience with"
# 5. Focus on concrete, searchable technical skills

# Return ONLY valid JSON in this EXACT format with proper comma placement:

# {{
#     "keywords": {{
#         "technical_skills": ["Python", "JavaScript", "SQL"],
#         "programming_languages": ["Python", "Java", "JavaScript"],
#         "tools_platforms": ["Git", "Docker", "AWS"],
#         "methodologies": ["Agile", "DevOps", "CI/CD"],
#         "soft_skills": ["Communication", "Leadership"],
#         "certifications": ["AWS Certified", "PMP"],
#         "domain_expertise": ["Data Analysis", "Web Development"]
#     }}
# }}

# CRITICAL JSON FORMATTING RULES:
# 1. Use double quotes around all keys and string values
# 2. Put commas after each array EXCEPT the last one in the object
# 3. NO trailing commas after the last item
# 4. NO comments or extra text outside the JSON
# 5. Return ONLY the JSON object, nothing else

# COMMON MISTAKES TO AVOID:
# ❌ Single quotes: {{'key': 'value'}} 
# ✅ Double quotes: {{"key": "value"}}
# ❌ Trailing comma: {{"key": ["item1", "item2",]}}
# ✅ No trailing comma: {{"key": ["item1", "item2"]}}
# ❌ Extra text: Here is the JSON: {{"key": "value"}}
# ✅ Only JSON: {{"key": "value"}}

# EXAMPLE FOR "Technical Specialist" - extract skills like:
# - Programming languages: Python, Java, SQL, JavaScript
# - Tools: Git, Docker, Jenkins, Tableau
# - Cloud: AWS, Azure, database management
# - Methodologies: Agile, problem-solving, data analysis

# Extract meaningful keywords that would help find qualified technical candidates, even if the job description is generic. Maximum 8 keywords per category."""

KEYWORD_EXTRACTION_PROMPT = """
You are an expert recruiter with deep knowledge across technical, managerial, functional, and hybrid roles.
Extract meaningful keywords from the job posting below for candidate matching.

JOB POSTING:
{job_posting}

EXTRACTION STRATEGY - BE COMPREHENSIVE AND INCLUSIVE:
1. ✅ Extract ALL relevant skills, tools, and qualifications mentioned (technical AND non-technical)
2. ✅ Include methodologies, frameworks, and approaches relevant to the role
3. ✅ Extract soft skills, leadership qualities, and interpersonal skills
4. ✅ Include certifications, qualifications, and education requirements
5. ✅ Extract domain knowledge and industry expertise
6. ✅ For any role type, infer common skills based on industry standards
7. ✅ Include both explicit and implicit requirements
8. ✅ Extract experience levels and seniority indicators
9. ✅ Include tools commonly used in similar roles (even if not explicitly mentioned)
10. ✅ ALWAYS extract at least 2-3 keywords per category when possible

INTELLIGENT EXTRACTION APPROACH:

1. **ANALYZE THE ROLE CONTEXT** - First understand what type of role this is and what industry/function it serves
2. **IDENTIFY CORE COMPETENCIES** - What are the main skills needed to succeed in this specific role?
3. **EXTRACT RELEVANT TOOLS** - What software, platforms, or systems would someone in this role typically use?
4. **DETERMINE METHODOLOGIES** - What processes, frameworks, or approaches are relevant to this role?
5. **ASSESS SOFT SKILLS** - What interpersonal and communication skills are important for this role?
6. **CONSIDER CERTIFICATIONS** - What qualifications or certifications would be valuable for this role?
7. **THINK DOMAIN EXPERTISE** - What industry knowledge or specialized areas are relevant?

EXTRACTION PRINCIPLES:
- **BE CONTEXTUAL** - Extract keywords that make sense for the specific role and industry
- **BE COMPREHENSIVE** - Include both obvious and subtle skill requirements
- **BE PRACTICAL** - Focus on skills that would actually help identify qualified candidates
- **BE ADAPTIVE** - Adjust your extraction based on the role level (entry, mid, senior, executive)
- **BE INCLUSIVE** - Consider both technical and non-technical skills as appropriate for the role

RETURN ONLY valid JSON in this EXACT format:
{{
    "keywords": {{
        "hard_skills": ["Python", "Data Analysis", "Project Management", "Software Development"],
        "tools_platforms": ["Jira", "AWS", "Excel", "SQL Server", "Git"],
        "methodologies": ["Agile", "Scrum", "ITIL", "DevOps"],
        "soft_skills": ["Communication", "Leadership", "Problem Solving", "Teamwork"],
        "certifications": ["PMP", "AWS Certified", "Scrum Master"],
        "domain_expertise": ["Healthcare", "Finance", "E-commerce", "Technical Support"]
    }}
}}

CRITICAL: You MUST extract at least 2-3 keywords in each category. If the job posting lacks specific details, infer reasonable keywords based on the role type and industry standards.

DYNAMIC EXTRACTION GUIDELINES:

**THINK LIKE A RECRUITER** - What keywords would you search for to find the best candidates for this specific role?

**CONSIDER THE ROLE LEVEL:**
- Entry-level: Focus on foundational skills, education, basic tools
- Mid-level: Include specialized skills, experience with specific tools/processes
- Senior-level: Add leadership, strategy, advanced certifications, industry expertise
- Executive-level: Emphasize strategic thinking, vision, governance, stakeholder management

**ADAPT TO INDUSTRY CONTEXT:**
- Healthcare: Include compliance, patient care, medical terminology, regulatory knowledge
- Finance: Include financial regulations, risk management, compliance, analytical skills
- Technology: Include programming, cloud platforms, development methodologies, security
- Education: Include curriculum development, student engagement, assessment, pedagogy
- Manufacturing: Include process optimization, quality control, safety, supply chain

**EXTRACT BASED ON ACTUAL JOB CONTENT:**
- What does this role actually DO day-to-day?
- What tools would they need to use?
- What knowledge would they need to have?
- What skills would make someone successful in this role?

DO NOT return empty arrays. Always extract meaningful keywords that would help find qualified candidates.
"""

KEYWORD_ANALYSIS_PROMPT = """You are an expert at analyzing keyword matches between job requirements and candidate resumes.

Job Keywords (from job posting):
{job_keywords}

Candidate Resume:
{resume_content}

Analyze which keywords from the job posting are present in the candidate's resume and provide a match analysis.

Return your analysis in JSON format:
{{
    "keyword_matches": {{
        "present_keywords": ["keyword1", "keyword2"],
        "missing_keywords": ["keyword3", "keyword4"],
        "partial_matches": ["keyword that partially matches"],
        "additional_relevant_skills": ["skills in resume not in job posting"]
    }},
    "match_statistics": {{
        "total_job_keywords": "number",
        "matched_keywords": "number", 
        "match_percentage": "percentage",
        "critical_missing": ["most important missing keywords"]
    }},
    "analysis": "Brief analysis of keyword match quality and gaps"
}}

Focus on identifying both exact matches and semantic/contextual matches."""

# KEYWORD_MATCHING_PROMPT = """You are an expert technical recruiter with deep knowledge of technology terminology. Analyze this resume to determine which specified keywords are present or demonstrated through the candidate's experience.

# RESUME CONTENT:
# {resume_content}

# KEYWORDS TO ANALYZE:
# {keywords_list}

# CRITICAL MATCHING RULES:
# 1. ✅ EXACT TECHNICAL MATCHES: Look for precise technology names, tools, frameworks
# 2. ✅ COMMON SYNONYMS: Accept standard variations (e.g., "JS" for "JavaScript", "ML" for "Machine Learning", "dotnet" for ".NET")
# 3. ✅ DEMONSTRATED EXPERIENCE: If they built REST APIs, they know "REST"
# 4. ✅ CONTEXTUAL EVIDENCE: "React development" indicates "React" knowledge
# 5. ✅ FRAMEWORK RELATIONSHIPS: Django usage implies Python knowledge
# 6. ❌ NO PARTIAL WORD MATCHES: ".NET" ≠ "network", "internet", or "ethernet"
# 7. ❌ NO SUBSTRING CONFUSION: "net" within other words does NOT mean ".NET"
# 8. ❌ BE STRICT: Only match if there's CLEAR, UNAMBIGUOUS evidence

# SPECIAL CASES TO WATCH:
# - ".NET" vs "network/internet/ethernet" - only match if specifically mentioned as framework
# - "React" vs "react" (verb) - only match if in technical context
# - "Python" vs snake references - only match in programming context
# - "Java" vs coffee/location references - only match in programming context

# Return ONLY a JSON object in this exact format:
# {{
#   "matched_keywords": ["list of keywords with CLEAR evidence in resume"],
#   "missing_keywords": ["list of keywords with NO evidence in resume"],
#   "analysis_notes": "brief explanation of strict matching logic used"
# }}

# Be highly accurate and conservative. False negatives are better than false positives."""

KEYWORD_MATCHING_PROMPT = """You are an expert recruiter with deep knowledge across multiple professional domains.  
Analyze the resume below to determine which of the specified keywords are present or clearly demonstrated through the candidate's experience.

RESUME CONTENT:
{resume_content}

KEYWORDS TO ANALYZE:
{keywords_list}

MATCHING GUIDELINES
1. ✅ EXACT MATCHES Find precise occurrences of each keyword (case or pluralization differences are acceptable).  
2. ✅ ACCEPTED VARIANTS Count standard abbreviations or acronyms (e.g., "PM" for "Project Manager").  
3. ✅ DEMONSTRATED EXPERIENCE If the candidate describes a task that inherently requires the keyword skill, count it (e.g., "prepared quarterly financial statements" ⇒ "financial reporting").  
4. ✅ CONTEXTUAL EVIDENCE Phrases that clearly imply the keyword within a professional context (e.g., "led Agile ceremonies" ⇒ "Agile").  
5. ✅ RELATED TERMS / FRAMEWORKS Use of a well-known tool or methodology may imply broader knowledge (e.g., "implemented SAP S/4HANA" ⇒ "SAP").  
6. ❌ NO PARTIAL WORD MATCHES Ignore the keyword if its letters merely appear inside unrelated words.  
7. ❌ NO SUBSTRING CONFUSION Reject instances where the keyword shows up only as part of a longer, different word.  
8. ❌ BE CONSERVATIVE Only match when evidence is clear and unambiguous—false negatives are preferable to false positives.

SPECIAL AMBIGUITY WATCH-OUTS
- Acronyms that double as common words or letters (e.g., "R" the language vs. the letter "r").  
- Words that can be verbs/adjectives vs. formal methodologies (e.g., "agile" description vs. "Agile" framework).  
- Brand or product names used in their professional sense (“Power BI" vs. "power" as a verb).

Return ONLY a JSON object in this exact format:
{{
  "matched_keywords": ["<keywords with clear evidence>"],
  "missing_keywords": ["<keywords with no evidence>"],
  "analysis_notes": "Brief explanation of the strict matching logic used."
}}

Maintain high accuracy and favor false negatives over false positives."""

# Ranking Prompts  
RANKING_PROMPT = """You are an expert HR recruiter tasked with intelligently ranking candidates based on how well they match the job requirements.

Job Posting:
{job_posting}

Candidates to rank:
{candidates_data}

Analyze each candidate and provide a ranking based on:
1. Technical skills match
2. Experience relevance and level
3. Education alignment
4. Overall job fit
5. Potential for success in the role

Return your analysis in JSON format:
{{
    "ranked_candidates": [
        {{
            "candidate_name": "Name",
            "rank": 1,
            "overall_score": "0-100",
            "ranking_rationale": "Why this candidate is ranked at this position",
            "key_strengths": ["strength1", "strength2"],
            "areas_of_concern": ["concern1", "concern2"]
        }}
    ],
    "ranking_methodology": "Brief explanation of how you ranked the candidates"
}}

Rank from best fit (rank 1) to least fit. Be objective and provide clear rationale for each ranking."""

# Job Description Prompts
COMPANY_OVERVIEW_PROMPT = """Generate a brief, professional company overview for a job posting. Keep it concise and engaging.

Company Name: {company_name}
Industry: {industry}

Provide a 2-3 sentence company overview that would be suitable for a job posting."""

JD_PROMPT = """You are an expert HR professional. Generate a comprehensive, well-structured job description based on the provided information.

Position: {position}
Company: {company}
Department: {department}
Location: {location}
Experience Level: {experience_level}
Employment Type: {employment_type}

Additional Requirements/Details:
{additional_info}

OUTPUT FORMAT — STRICT:
Return ONLY clean semantic HTML. No markdown (no `**`, no `##`, no `---`, no backticks). No <html>, <head>, <body>, <style>, <script>, or code fences. Output starts directly with the <h1>.

Use this exact structure and these exact tags (omit the meta line items that have no value provided):

<h1>{position}</h1>
<p class="jd-meta"><strong>Department:</strong> {department} | <strong>Location:</strong> {location} | <strong>Experience Level:</strong> {experience_level} | <strong>Employment Type:</strong> {employment_type}</p>

<h2>Company Overview</h2>
<p>2-4 sentences about the company, drawn from the company information provided.</p>

<h2>Position Summary</h2>
<p>2-4 sentences describing the role, its impact, and who it's for.</p>

<h2>Key Responsibilities</h2>
<ul>
  <li>5-8 specific, action-oriented responsibilities, each one sentence.</li>
</ul>

<h2>Required Qualifications</h2>
<ul>
  <li>5-7 must-have qualifications (education, years of experience, core technical skills).</li>
</ul>

<h2>Preferred Qualifications</h2>
<ul>
  <li>3-5 nice-to-have qualifications.</li>
</ul>

<h2>Skills Required</h2>
<p><strong>Technical Skills:</strong></p>
<ul><li>Concrete technical skills, frameworks, tools.</li></ul>
<p><strong>Soft Skills:</strong></p>
<ul><li>Concrete soft skills.</li></ul>

<h2>Benefits and Perks</h2>
<ul>
  <li>4-6 specific benefits.</li>
</ul>

<h2>Application Instructions</h2>
<p>One short paragraph telling candidates how to apply.</p>

RULES:
- Every <li> must be a complete sentence with a period.
- Use plain text inside tags. Do NOT include literal asterisks, hashes, or "###".
- Do NOT wrap the output in ```html or any code fence.
- Do NOT add inline styles, classes (other than jd-meta on the meta paragraph), or IDs.
- Be specific to the position and company; avoid generic filler.
"""

ENHANCE_PROMPT = """You are an expert HR professional. Enhance and improve the following job description to make it more compelling, clear, and comprehensive.

Current Job Description:
{job_description}

Please enhance this job description by:
1. Improving clarity and readability
2. Making it more engaging and attractive to candidates
3. Ensuring all important sections are covered
4. Optimizing keywords for better searchability
5. Adding any missing critical information
6. Improving the overall structure and flow

Return the enhanced job description in a professional format."""

JD_KEYWORD_PROMPT = """Extract the most important keywords from this job description for search and matching purposes.

Job Description:
{job_description}

Return a JSON array of the most relevant keywords:
{{"keywords": ["keyword1", "keyword2", "keyword3"]}}""" 