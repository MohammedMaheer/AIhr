"""
LLM Prompts Module

This module contains all prompts used for LLM interactions in the HR Agent application.
Organized by functionality for better maintainability and reusability.
"""

from typing import List, Dict, Any


# =============================================================================
# RESUME ANALYSIS PROMPTS
# =============================================================================

def get_file_analysis_prompt(query: str) -> str:
    """Generate prompt for direct file analysis with Gemini"""
    return f"""
        You are an expert HR recruiter and resume analyst. I'm sending you a resume file to analyze against a search query.

        SEARCH QUERY/JOB REQUIREMENT:
        {query}

        Please extract the text from this file and provide analysis in the following JSON format ONLY. Do not include any other text or explanation outside the JSON:

        {{
            "candidate_name": "Full name of the candidate",
            "phone": "Phone number if available",
            "email": "Email address if available",
            "location": "Location/City if available",
            "current_role": "Current job title or role",
            "experience_years": "Years of experience (number only, or 'Not specified')",
            "match_score": 95,
            "matching_skills": ["skill1", "skill2", "skill3"],
            "key_strengths": ["strength1", "strength2", "strength3"],
            "missing_elements": ["missing1", "missing2"],
            "relevant_experience": "Brief description of most relevant work experience",
            "best_match_reason": "Why this candidate is a good match in 1-2 sentences",
            "recommendations": ["recommendation1", "recommendation2"],
            "summary": "Brief 2-3 sentence summary of the match quality"
        }}

        Extract all information accurately from the resume. If any field is not available, use "Not available" or empty array as appropriate. The match_score should be between 0-100 based on how well the resume matches the search query.
        """


def get_resume_text_analysis_prompt(query: str, resume_content: str) -> str:
    """Generate prompt for resume text analysis"""
    return f"""
        You are an expert HR recruiter and resume analyst. I need you to analyze a resume against a specific job requirement or search query.

        SEARCH QUERY/JOB REQUIREMENT:
        {query}

        RESUME CONTENT:
        {resume_content}

        Please extract the candidate information and provide analysis in the following JSON format ONLY. Do not include any other text or explanation outside the JSON:

        {{
            "candidate_name": "Full name of the candidate",
            "phone": "Phone number if available",
            "email": "Email address if available",
            "location": "Location/City if available",
            "current_role": "Current job title or role",
            "experience_years": "Years of experience (number only, or 'Not specified')",
            "match_score": 95,
            "matching_skills": ["skill1", "skill2", "skill3"],
            "key_strengths": ["strength1", "strength2", "strength3"],
            "missing_elements": ["missing1", "missing2"],
            "relevant_experience": "Brief description of most relevant work experience",
            "best_match_reason": "Why this candidate is a good match in 1-2 sentences",
            "recommendations": ["recommendation1", "recommendation2"],
            "summary": "Brief 2-3 sentence summary of the match quality"
        }}

        Extract all information accurately from the resume. If any field is not available, use "Not available" or empty array as appropriate. The match_score should be between 0-100 based on how well the resume matches the search query.
        """


# =============================================================================
# ENTITY EXTRACTION PROMPTS
# =============================================================================

def get_entity_extraction_prompt(resume_content: str) -> str:
    """Generate prompt for extracting candidate entities from resume"""
    return f"""Extract candidate information from this resume and return ONLY a valid JSON object.

RESUME:
{resume_content}

Return exactly this JSON format:
{{
  "candidate_overview": {{
    "name": "Full Name",
    "location": "City, Country", 
    "email": "email@domain.com",
    "phone": "phone number",
    "current_role": "Current Position",
    "experience_years": "5 Years"
  }},
  "technical_skills": ["Python", "SQL", "Machine Learning"],
  "tools_technologies": ["AWS", "Docker", "TensorFlow"],
  "education": {{
    "degree": "Bachelor of Science",
    "university": "University Name",
    "graduation_year": "2020"
  }},
  "work_experience": [
    {{
      "year_range": "2020-2024",
      "role": "Data Scientist", 
      "company": "Company Name",
      "key_responsibilities": ["Built models", "Analyzed data"]
    }}
  ]
}}

Rules:
- Return ONLY the JSON object
- Use "Not available" for missing information
- Keep arrays simple with 3-5 items maximum
- No explanations or markdown formatting"""


# =============================================================================
# HR SCORECARD PROMPTS
# =============================================================================

def get_basic_scorecard_prompt(query: str, job_title: str, candidate_name: str, 
                              candidate_location: str, candidate_experience: str,
                              candidate_email: str, candidate_phone: str, entities: Dict[str, Any]) -> str:
    """Generate prompt for basic HR scorecard generation"""
    return f"""Compare this candidate with job requirements and create an enhanced HR scorecard with role suggestions and tenure predictions.

JOB REQUIREMENTS:
{query}

CANDIDATE:
Name: {candidate_name}
Experience: {candidate_experience}
Skills: {', '.join(entities.get('technical_skills', [])[:5])}
Tools: {', '.join(entities.get('tools_technologies', [])[:5])}
Education: {entities.get('education', {}).get('degree', 'Not available')}
Work History: {', '.join([f"{exp.get('company', 'Company')} ({exp.get('duration', 'Duration')})" for exp in entities.get('work_experience', [])[:3]])}

Create this exact JSON format:
{{
  "candidate_overview": {{
    "name": "{candidate_name}",
    "location": "{candidate_location}",
    "experience_years": "{candidate_experience}",
    "position_applied_for": "{job_title}",
    "email": "{candidate_email}",
    "phone": "{candidate_phone}",
    "overall_match_score": 85,
    "match_status": "Strong Fit"
  }},
  "score_breakdown": {{
    "primary_competency": {{
      "score": 90,
      "comment": "Assessment of main skills for this role"
    }},
    "secondary_competency": {{
      "score": 85,
      "comment": "Assessment of supporting skills"
    }},
    "experience_relevance": {{
      "score": 80,
      "comment": "How well experience matches requirements"
    }}
  }},
  "analysis_summary": {{
    "ai_analysis": "Brief summary of candidate fit and key strengths based on detailed assessment",
    "resume_highlights": [
      "Key achievement or skill from resume",
      "Notable project or accomplishment",
      "Relevant experience or certification"
    ]
  }},

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
      }}
    }},
    }}
}}

Rules:
- Score 80-100 = Strong Fit, 60-79 = Medium Fit, 0-59 = Weak Fit
- DYNAMIC SCORE CATEGORIES: Choose appropriate category names based on role type (EXACTLY 3 categories):
  * For TECHNICAL roles: "technical_skills", "problem_solving", "system_design"
  * For MANAGEMENT roles: "leadership_experience", "strategic_thinking", "team_management"
  * For SALES roles: "relationship_building", "negotiation_skills", "target_achievement" 
  * For MARKETING roles: "creative_skills", "analytics_knowledge", "brand_management"
  * For HR roles: "people_management", "policy_knowledge", "organizational_skills"
  * For FINANCE roles: "financial_analysis", "regulatory_knowledge", "attention_to_detail"
  * For OTHER roles: Choose the 3 most relevant categories for that specific role
- Tenure prediction should consider job-hopping patterns and career stability
- Analyze work history duration patterns for tenure scoring
- Keep all comments specific and actionable
- Return ONLY the JSON object"""


def get_comprehensive_hr_scorecard_prompt(query: str, job_title: str, resume_content: str) -> str:
    """Generate prompt for comprehensive HR scorecard analysis"""
    return f"""
            You are an expert HR professional conducting resume screening. Analyze this resume against the job requirements and create a comprehensive HR scorecard for decision-making.

            JOB REQUIREMENTS:
            {query}

            RESUME CONTENT:
            {resume_content}

            Generate a detailed HR scorecard in the following JSON format ONLY:

            {{
                "candidate_overview": {{
                    "name": "Full candidate name",
                    "location": "City, State/Country or Remote",
                    "experience_years": "X Years",
                    "position_applied_for": "{job_title}",
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
                    "keyword_technical_match": {{
                        "score": 70,
                        "comment": "Assessment of specific technical keywords and tools mentioned in job requirements vs resume content"
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
                "recommendations": {{
                    "action": "Shortlist",
                    "priority": "High",
                    "next_steps": ["Technical interview", "Leadership assessment"],
                    "strengths": ["Strong technical foundation", "Proven leadership"]
                }},

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
                        }}
                    }},
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

            IMPORTANT GUIDELINES:
            1. Extract ALL contact information accurately from the resume
            2. Calculate realistic scores based on actual resume content vs job requirements
            3. Match Status should be: "Strong Fit" (80-100%), "Medium Fit" (60-79%), "Weak Fit" (<60%)
            
            4. DYNAMIC SCORE CATEGORIES: Choose appropriate category names in score_breakdown based on the role type (EXACTLY 4 categories - including keyword_technical_match):
            - For TECHNICAL roles (Developer, Engineer, Data Scientist): "technical_skills", "problem_solving", "system_design", "keyword_technical_match"
            - For MANAGEMENT roles (Manager, Director, VP): "leadership_experience", "strategic_thinking", "team_management", "keyword_technical_match" 
            - For SALES roles: "relationship_building", "negotiation_skills", "target_achievement", "keyword_technical_match"
            - For MARKETING roles: "creative_skills", "analytics_knowledge", "brand_management", "keyword_technical_match"
            - For HR roles: "people_management", "policy_knowledge", "organizational_skills", "keyword_technical_match"
            - For FINANCE roles: "financial_analysis", "regulatory_knowledge", "attention_to_detail", "keyword_technical_match"
            - For DESIGN roles: "design_skills", "creative_thinking", "user_experience", "keyword_technical_match"
            - For OPERATIONS roles: "process_improvement", "project_management", "analytical_thinking", "keyword_technical_match"
            - For CONSULTING roles: "analytical_skills", "client_management", "problem_solving", "keyword_technical_match"
            - For CUSTOMER SERVICE roles: "communication_skills", "problem_resolution", "empathy", "keyword_technical_match"
            
            5. CRITICAL: The "keyword_technical_match" score should assess how well the candidate's resume mentions specific technical terms, tools, technologies, and keywords from the job requirements
            6. Provide specific, actionable comments for each score category that relate to the chosen categories
            7. Include actual resume snippets that demonstrate key qualifications
            8. Create realistic career timeline from resume work history
            9. The keyword_coverage section will be populated automatically with standardized analysis - leave it empty for now
            10. AI summary should be 3-4 sentences highlighting fit and key strengths
            11. Benchmark position should reflect realistic ranking
            12. TENURE PREDICTION: Analyze job history patterns to predict how long they might stay (consider average tenure at previous roles, career stability, growth trajectory)
            13. RETENTION ANALYSIS: Identify specific risks and strategies based on candidate's background and career stage
            14. Tenure prediction should be realistic (1-2 years, 2-4 years, 3-5 years, 5+ years) based on their job history patterns
            15. ALWAYS use exactly 4 relevant score categories that make sense for the specific role being analyzed (including keyword_technical_match)
            16. SCORING LOGIC: Base the overall_match_score on a weighted average of the 4 breakdown scores, with keyword_technical_match having significant weight (25-30%)
            """


# =============================================================================
# KEYWORD ANALYSIS PROMPTS
# =============================================================================

def get_single_query_keyword_extraction_prompt(query: str) -> str:
    """Generate prompt for extracting keywords from job posting"""
    return f"""Extract ONLY the important keywords that already exist in this job posting. DO NOT add any new terms. Return ONLY valid JSON:

JOB POSTING: "{query}"

Return this JSON structure:
{{
    "optimized_query": "extracted keywords from the original job posting only",
    "extracted_info": {{
        "experience_years": "5+ years or Not specified",
        "seniority_level": "Junior/Mid/Senior/Lead or Not specified", 
        "key_skills": ["skill1", "skill2", "skill3"],
        "job_titles": ["title1", "title2"],
        "domain_areas": ["domain1", "domain2"]
    }}
}}

CRITICAL RULES for optimized_query:
- ONLY use words and phrases that appear in the original job posting
- Extract technical skills, tools, frameworks, programming languages THAT ARE MENTIONED
- Extract experience level and years IF MENTIONED in the original text
- Extract job titles and role names THAT ARE MENTIONED
- Extract domain areas THAT ARE MENTIONED
- Remove duplicate words
- DO NOT add synonyms, related terms, or new words
- DO NOT add generic terms like "professional", "skilled", "experienced" unless they appear in original
- Target 50-100 words from the original text only
- Keep only the most important keywords from the source text"""


def get_standardized_keyword_extraction_prompt(query: str) -> str:
    """Generate prompt for extracting standardized keywords from job description"""
    return f"""You are an expert technical recruiter. Extract ONLY the most relevant, specific, and meaningful keywords from this job description for candidate matching.

JOB DESCRIPTION: "{query}"

CRITICAL INSTRUCTIONS:
1. Extract ONLY concrete, specific technical skills and qualifications
2. Avoid generic job description language and experience requirements
3. Focus on technologies, tools, programming languages, and methodologies
4. DO NOT extract phrases like "building scalable applications", "5+ years experience", "Senior level"
5. Extract SPECIFIC terms like "React", "Python", "AWS", "Docker", "Agile"
6. Avoid duplicates and similar variations
7. NO experience level terms like "senior", "junior", "experienced"
8. NO generic phrases like "web applications", "scalable systems"

Return ONLY a JSON object in this exact format:
{{"keywords": {{
    "technical_skills": ["specific technologies, frameworks, platforms"],
    "programming_languages": ["exact programming languages mentioned"], 
    "tools_platforms": ["development tools, cloud platforms, databases"],
    "methodologies": ["development methodologies, practices"],
    "soft_skills": ["leadership qualities, communication skills"],
    "certifications": ["specific certifications mentioned"],
    "domain_expertise": ["industry knowledge, business domains"]
}}}}

WHAT TO EXTRACT:
✅ Programming languages: Python, JavaScript, Java, TypeScript, SQL, R, C++, Go
✅ Frameworks/Libraries: React, Angular, Django, Spring, TensorFlow, PyTorch
✅ Cloud platforms: AWS, Azure, GCP, Docker, Kubernetes  
✅ Databases: PostgreSQL, MongoDB, MySQL, Redis, Elasticsearch
✅ Tools: Git, Jenkins, Jira, Tableau, Power BI, Terraform
✅ Methodologies: Agile, Scrum, DevOps, CI/CD, TDD, Microservices
✅ Certifications: AWS Certified, Azure Certified, PMP, Scrum Master
✅ Soft skills: Leadership, Communication, Problem-solving, Analytical thinking
✅ Domain expertise: Machine Learning, Data Science, Finance, Healthcare

WHAT NOT TO EXTRACT:
❌ Experience requirements: "5+ years", "senior level", "experienced", "junior"
❌ Generic phrases: "building scalable applications", "web applications", "scalable"
❌ Job description filler: "ideal candidate", "looking for", "join our team"
❌ Vague descriptors: "strong", "excellent", "good knowledge", "proficient"
❌ Company-specific: "our platform", "our stack", "we use"
❌ Generic terms: "development", "programming", "software", "technical"

Maximum 8 keywords per category. Return ONLY the JSON object with NO additional text."""


def get_keyword_analysis_prompt(resume_content: str, standardized_keywords: List[str]) -> str:
    """Generate prompt for analyzing keyword matches in resume"""
    return f"""You are an expert technical recruiter. Analyze this resume and determine which of the specified keywords are present or demonstrated through the candidate's experience.

RESUME CONTENT:
{resume_content}...

KEYWORDS TO ANALYZE:
{', '.join(standardized_keywords)}

MATCHING RULES:
1. Look for EXACT matches of technology names, tools, frameworks
2. Look for SYNONYMS and VARIATIONS (e.g., "JS" for "JavaScript", "ML" for "Machine Learning")
3. Look for DEMONSTRATED EXPERIENCE (e.g., if they built REST APIs, they know "REST")
4. Look for RELATED EXPERIENCE (e.g., if they used "Django", they likely know "Python")
5. Consider CONTEXT (e.g., "React development" means they know "React")
6. Be INTELLIGENT about abbreviations and full forms
7. Consider SKILL LEVELS mentioned (e.g., "Advanced Python" means they know "Python")

Return ONLY a JSON object in this exact format:
{{
  "matched_keywords": ["list of keywords found in resume"],
  "missing_keywords": ["list of keywords NOT found in resume"],
  "analysis_notes": "brief explanation of matching logic"
}}

Be thorough but accurate. Only mark keywords as matched if there's clear evidence in the resume."""


# =============================================================================
# RANKING PROMPTS
# =============================================================================

def get_ranking_prompt(original_query: str, keywords_data: Dict[str, Any], candidates_for_ranking: List[Dict]) -> str:
    """Generate prompt for ranking candidates based on job requirements"""
    import json
    
    return f"""
        You are an expert HR recruiter. You need to intelligently rank these candidates based on how well they match the job requirements.

        ORIGINAL JOB QUERY: "{original_query}"
        
        EXTRACTED REQUIREMENTS:
        - Primary Keywords: {keywords_data.get('primary_keywords', [])}
        - Required Skills: {keywords_data.get('required_skills', [])}
        - Experience Level: {keywords_data.get('experience_level', 'Any')}
        - Job Titles: {keywords_data.get('job_titles', [])}

        CANDIDATES TO RANK:
        {json.dumps(candidates_for_ranking, indent=2)}

        Please provide a ranking with updated scores in the following JSON format ONLY:

        {{
            "ranked_candidates": [
                {{
                    "index": 0,
                    "final_score": 95,
                    "ranking_reason": "Excellent match because...",
                    "key_strengths": ["strength1", "strength2"],
                    "concerns": ["concern1", "concern2"]
                }}
            ],
            "ranking_summary": "Brief explanation of the ranking methodology used"
        }}

        Consider:
        1. Exact skill matches vs. related skills
        2. Experience level appropriateness
        3. Job title relevance
        4. Overall candidate quality
        5. Potential for growth/adaptation

        Rank from highest to lowest match quality. Scores should be between 0-100.
        """


# =============================================================================
# JOB DESCRIPTION PROMPTS
# =============================================================================

def get_jd_generation_prompt(job_details: Dict[str, Any]) -> str:
    """Generate prompt for creating job descriptions"""
    job_title = job_details.get('job_title', '')
    department = job_details.get('department', '')
    location = job_details.get('location', '')
    experience_level = job_details.get('experience_level', '')
    employment_type = job_details.get('employment_type', 'full-time')
    description = job_details.get('description', '')
    skills = job_details.get('skills', [])
    
    # Build company context if available
    company_context = ""
    if job_details.get('company_name'):
        company_context += f"\n\nCOMPANY INFORMATION:\n"
        company_context += f"Company: {job_details['company_name']}\n"
        if job_details.get('company_info'):
            company_context += f"About the Company: {job_details['company_info']}\n"
    
    return f"""
        You are an expert HR professional and job description writer. Generate a comprehensive, professional job description based on the following requirements:

        JOB INFORMATION:
        - Job Title: {job_title}
        - Department: {department}
        - Location: {location}
        - Experience Level: {experience_level}
        - Employment Type: {employment_type}
        {company_context}
        
        ADDITIONAL REQUIREMENTS:
        {description}
        
        REQUIRED SKILLS:
        {', '.join(skills) if skills else 'Not specified'}
        
        Please generate a professional job description with the following structure in HTML format:
        
        1. Job Title and Company Overview (incorporate company information naturally if provided)
        2. Position Summary (2-3 sentences)
        3. Key Responsibilities (5-8 bullet points)
        4. Required Qualifications (education, experience, skills)
        5. Preferred Qualifications (nice-to-have skills)
        6. What We Offer (benefits, growth opportunities - tailor to company culture if known)
        7. How to Apply
        
        Make it engaging, specific, and attractive to potential candidates. Use modern, inclusive language. Include industry-specific terminology where appropriate. If company information is provided, naturally incorporate the company's values, mission, and culture throughout the job description to make it more personalized and compelling.
        
        Format the response as clean HTML with proper headings (h2, h3), lists (ul, li), and paragraphs (p). Do not include <html>, <head>, or <body> tags - just the content.
        """


def get_jd_enhancement_prompt(existing_content: str, skills: List[str] = None) -> str:
    """Generate prompt for enhancing job descriptions"""
    skills_text = f"\nAdditional skills to incorporate: {', '.join(skills)}" if skills else ""
    
    return f"""
        You are an expert HR professional. Please enhance and improve the following job description to make it more compelling, comprehensive, and professional.
        
        CURRENT JOB DESCRIPTION:
        {existing_content}
        {skills_text}
        
        Please enhance this job description by:
        1. Improving the language to be more engaging and professional
        2. Adding missing sections if needed (responsibilities, qualifications, benefits)
        3. Making it more inclusive and appealing to diverse candidates
        4. Ensuring proper structure and formatting
        5. Adding industry best practices and modern terminology
        6. Incorporating the additional skills if provided
        
        Return the enhanced job description in clean HTML format with proper headings (h2, h3), lists (ul, li), and paragraphs (p). Do not include <html>, <head>, or <body> tags - just the content.
        
        Keep the core information but significantly improve the presentation and completeness.
        """


def get_jd_keyword_extraction_prompt(content: str) -> str:
    """Generate prompt for extracting keywords from job descriptions"""
    return f"""
        You are an expert HR analyst. Analyze the following job description or requirements and extract the most important keywords and skills.
        
        CONTENT TO ANALYZE:
        {content}
        
        Please extract and categorize the following:
        1. Technical Skills (programming languages, tools, technologies)
        2. Soft Skills (communication, leadership, etc.)
        3. Qualifications (degrees, certifications, years of experience)
        4. Industry Keywords (domain-specific terms)
        
        Return ONLY a JSON object with this exact structure:
        {{
            "keywords": ["skill1", "skill2", "skill3", "..."],
            "technical_skills": ["tech1", "tech2", "..."],
            "soft_skills": ["soft1", "soft2", "..."],
            "qualifications": ["qual1", "qual2", "..."],
            "industry_terms": ["term1", "term2", "..."]
        }}
        
        Provide 5-15 items in each category. Focus on the most relevant and important terms. Do not include any text outside the JSON object.
        """ 