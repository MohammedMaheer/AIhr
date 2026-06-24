// Authentication and user management functions
async function checkAuthAndLoadUser() {
    try {
        const response = await fetch('/api/me');
        if (!response.ok) {
            // Not authenticated, redirect to login
            window.location.href = '/login';
            return;
        }

        const data = await response.json();
        const user = data.user;

        // Update user info in UI
        document.getElementById('userName').textContent = user.full_name;
        document.getElementById('userEmail').textContent = user.email;

        // Store user info for later use
        window.currentUser = user;

        // Show/hide admin links based on user type
        if (user.user_type === 'super_admin' || user.user_type === 'tenant_admin') {
            // Admin users can see dashboard
            document.getElementById('dashboard-link').style.display = 'flex';
        }

        // If dashboard is currently loaded, reinitialize it with user data
        setTimeout(() => {
            const currentPage = document.getElementById('main-content').innerHTML;
            if (currentPage.includes('admin-dashboard') || currentPage.includes('user-dashboard')) {
                console.log('Reinitializing dashboard after user data loaded');
                if (typeof window.initializeDashboard === 'function') {
                    window.initializeDashboard();
                }
            }
        }, 200);

    } catch (error) {
        console.error('Auth check failed:', error);
        window.location.href = '/login';
    }
}

// Toggle user menu
function toggleUserMenu() {
    const dropdown = document.getElementById('userDropdown');
    dropdown.classList.toggle('hidden');
}

// Logout function
async function logout() {
    try {
        await fetch('/api/logout', { method: 'POST' });
        window.location.href = '/login';
    } catch (error) {
        console.error('Logout error:', error);
    }
}

document.addEventListener('DOMContentLoaded', function () {
    // Check authentication first
    checkAuthAndLoadUser();

    const dashboardLink = document.getElementById('dashboard-link');
    const searchResumesLink = document.getElementById('search-resumes-link');
    const jdBuilderLink = document.getElementById('jd-builder-link');
    const vectorSearchLink = document.getElementById('vector-search-link');
    const historyLink = document.getElementById('history-link');
    const uploadFilesLink = document.getElementById('upload-files-link');
    const settingsLink = document.getElementById('settings-link');
    const mainContent = document.getElementById('main-content');
    // const pageTitle = document.getElementById('page-title');

    // Search history storage
    let searchHistory = JSON.parse(localStorage.getItem('searchHistory') || '[]');

    const pages = {
        vectorSearch: `
            <div class="p-4 h-full overflow-y-auto bg-gray-50">
                <div class="max-w-4xl mx-auto">
                    <!-- Header Section -->
                    <div class="mb-6">
                        <div class="flex items-center justify-between">
                            <div>
                                <h2 class="text-2xl font-bold text-gray-900">Vector Search Test</h2>
                                <p class="mt-1 text-gray-600 text-sm">Test the vector search index directly</p>
                            </div>
                            <div class="flex items-center space-x-2">
                                <div class="px-3 py-1 bg-green-100 text-green-800 rounded-full text-xs font-medium">
                                    <i class="fas fa-database mr-1"></i>
                                    resume-index
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Search Form -->
                    <div class="bg-white rounded-xl p-6 shadow-sm border border-gray-200 mb-6">
                        <div class="mb-4">
                            <label for="vectorQuery" class="block text-sm font-medium text-gray-700 mb-2">
                                Search Query
                            </label>
                            <div class="relative">
                                <input type="text" 
                                       id="vectorQuery" 
                                       class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                       placeholder="Enter your search query (e.g., 'Python developer with machine learning experience')"
                                       autocomplete="off">
                                <div class="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
                                    <i class="fas fa-search text-gray-400"></i>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Search Options -->
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-2">Search Method</label>
                            <div class="flex items-center space-x-4">
                                <label class="flex items-center">
                                    <input type="radio" name="searchMethod" value="single" checked class="mr-2 text-blue-600">
                                    <span class="text-sm text-gray-700">Single Query</span>
                                </label>
                                <label class="flex items-center">
                                    <input type="radio" name="searchMethod" value="multi" class="mr-2 text-blue-600">
                                    <span class="text-sm text-gray-700">4-Query Search (Experience + Skills + Role + Domain)</span>
                                </label>
                                <label class="flex items-center">
                                    <input type="radio" name="searchMethod" value="enhanced" class="mr-2 text-blue-600">
                                    <span class="text-sm text-gray-700">Enhanced LLM Pipeline</span>
                                </label>
                                <label class="flex items-center">
                                    <input type="radio" name="searchMethod" value="hr-scorecard" class="mr-2 text-blue-600">
                                    <span class="text-sm text-gray-700">📊 HR Scorecard Analysis</span>
                                </label>
                            </div>
                        </div>
                        
                        <!-- Job Title Input (for HR Scorecard) -->
                        <div id="jobTitleSection" class="hidden mb-4">
                            <label for="jobTitle" class="block text-sm font-medium text-gray-700 mb-2">
                                Job Title/Position
                            </label>
                            <input type="text" 
                                   id="jobTitle" 
                                   class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                   placeholder="e.g., Senior Data Scientist, Full Stack Developer"
                                   autocomplete="off">
                        </div>
                        
                        <div class="flex items-center justify-between">
                            <div class="flex items-center space-x-3">
                            <button id="vectorSearchBtn" 
                                    class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
                                <i class="fas fa-search mr-2"></i>
                                Search Vector Store
                            </button>
                                
                                <select id="resultCount" class="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                                    <option value="5">5 Results</option>
                                    <option value="10">10 Results</option>
                                    <option value="15" selected>15 Results</option>
                                    <option value="20">20 Results</option>
                                </select>
                            </div>
                            
                            <div class="flex items-center space-x-4">
                                <button id="sampleQueriesBtn" 
                                        class="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors text-sm font-medium">
                                    <i class="fas fa-lightbulb mr-2"></i>
                                    Sample Queries
                                </button>
                                <button id="clearResultsBtn" 
                                        class="px-4 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition-colors text-sm font-medium">
                                    <i class="fas fa-trash mr-2"></i>
                                    Clear Results
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- Sample Queries -->
                    <div id="sampleQueriesSection" class="hidden bg-blue-50 rounded-xl p-6 border border-blue-200 mb-6">
                        <h3 class="text-lg font-semibold text-blue-900 mb-4">Sample Queries</h3>
                        <div class="mb-4">
                            <h4 class="text-sm font-medium text-blue-800 mb-2">Short Queries (Recommended for Single Query method):</h4>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
                            <button class="sample-query-btn text-left p-3 bg-white rounded-lg border border-blue-200 hover:bg-blue-50 transition-colors">
                                <i class="fas fa-code text-blue-600 mr-2"></i>
                                    Python machine learning engineer
                            </button>
                            <button class="sample-query-btn text-left p-3 bg-white rounded-lg border border-blue-200 hover:bg-blue-50 transition-colors">
                                <i class="fas fa-laptop-code text-blue-600 mr-2"></i>
                                    Senior React JavaScript developer
                            </button>
                            <button class="sample-query-btn text-left p-3 bg-white rounded-lg border border-blue-200 hover:bg-blue-50 transition-colors">
                                <i class="fas fa-chart-bar text-blue-600 mr-2"></i>
                                    Data scientist PhD statistics
                            </button>
                            <button class="sample-query-btn text-left p-3 bg-white rounded-lg border border-blue-200 hover:bg-blue-50 transition-colors">
                                <i class="fas fa-cloud text-blue-600 mr-2"></i>
                                    DevOps AWS kubernetes docker
                            </button>
                            </div>
                        </div>
                        
                        <div>
                            <h4 class="text-sm font-medium text-blue-800 mb-2">Full Requirements (Use Multi-Query or Enhanced method):</h4>
                            <div class="space-y-2">
                                <button class="sample-query-btn text-left p-3 bg-white rounded-lg border border-blue-200 hover:bg-blue-50 transition-colors w-full">
                                    <i class="fas fa-briefcase text-blue-600 mr-2"></i>
                                    <div class="text-sm">
                                        <strong>Senior Data Scientist - AI/ML</strong><br>
                                        We're seeking a Senior Data Scientist with 5+ years experience in machine learning, Python, TensorFlow/PyTorch, and statistical modeling. Must have PhD or Masters in Data Science, Statistics, or related field. Experience with cloud platforms (AWS/GCP), big data tools (Spark, Hadoop), and deep learning for NLP/computer vision preferred.
                                    </div>
                            </button>
                                <button class="sample-query-btn text-left p-3 bg-white rounded-lg border border-blue-200 hover:bg-blue-50 transition-colors w-full">
                                    <i class="fas fa-code text-blue-600 mr-2"></i>
                                    <div class="text-sm">
                                        <strong>Full Stack Developer - React/Node.js</strong><br>
                                        Looking for a Full Stack Developer with 3+ years building modern web applications. Required: React.js, Node.js, TypeScript, RESTful APIs, SQL/NoSQL databases. Experience with AWS/Azure, microservices architecture, Docker, CI/CD pipelines, and Agile methodologies highly valued.
                                    </div>
                                </button>
                                <button class="sample-query-btn text-left p-3 bg-white rounded-lg border border-blue-200 hover:bg-blue-50 transition-colors w-full">
                                    <i class="fas fa-server text-blue-600 mr-2"></i>
                                    <div class="text-sm">
                                        <strong>DevOps Engineer - Cloud Infrastructure</strong><br>
                                        DevOps Engineer needed with expertise in cloud infrastructure automation. Must have experience with AWS/GCP, Kubernetes, Docker, Terraform, Jenkins/GitLab CI. Knowledge of monitoring tools (Prometheus, Grafana), scripting (Python/Bash), and security best practices required.
                                    </div>
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- Loading State -->
                    <div id="vectorSearchLoading" class="hidden bg-white rounded-xl p-8 shadow-sm border border-gray-200 mb-6">
                        <div class="flex items-center justify-center">
                            <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mr-3"></div>
                            <span class="text-gray-600">Searching vector store...</span>
                        </div>
                    </div>

                    <!-- Results Section -->
                    <div id="vectorSearchResults" class="hidden">
                        <div class="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                            <div class="flex items-center justify-between mb-6">
                                <div>
                                    <h3 class="text-lg font-semibold text-gray-900">Search Results</h3>
                                    <p id="resultsSubtitle" class="text-sm text-gray-600"></p>
                                </div>
                                <div class="flex items-center space-x-2 text-sm text-gray-500">
                                    <i class="fas fa-clock"></i>
                                    <span id="searchTime"></span>
                                </div>
                            </div>
                            <div id="resultsContainer" class="space-y-4">
                                <!-- Results will be populated here -->
                            </div>
                        </div>
                    </div>

                    <!-- No Results State -->
                    <div id="noResults" class="hidden bg-white rounded-xl p-8 shadow-sm border border-gray-200 text-center">
                        <div class="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                            <i class="fas fa-search text-gray-400 text-xl"></i>
                        </div>
                        <h3 class="text-lg font-medium text-gray-900 mb-2">No Results Found</h3>
                        <p class="text-gray-600 mb-4">Try adjusting your search query or using different keywords.</p>
                        <button id="noResultsSamplesBtn" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                            Try Sample Queries
                        </button>
                    </div>
                </div>
            </div>
        `,
        dashboard: `
            <!-- Tenant User Dashboard -->
            <div id="user-dashboard" class="p-4 h-full overflow-y-auto bg-gray-50" style="display: none;">
                <div class="max-w-7xl mx-auto">
                    <!-- Resource Usage Section (for tenant users) -->
                    <div id="resource-usage-section" class="hidden mb-6">
                        <div class="bg-gradient-to-r from-blue-600 to-purple-600 rounded-xl p-6 text-white shadow-lg">
                            <h3 class="text-xl font-bold mb-4 flex items-center">
                                <i class="fas fa-chart-bar mr-2"></i>All Recruitment Details
                            </h3>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <!-- Resume Usage -->
                                <div class="bg-white/10 rounded-lg p-4 backdrop-blur-sm">
                                    <div class="flex items-center justify-between mb-2">
                                        <span class="text-sm font-medium">Resume Storage</span>
                                        <span class="text-xs bg-white/20 px-2 py-1 rounded" id="resume-usage-percent">0%</span>
                                    </div>
                                    <div class="flex items-center justify-between text-2xl font-bold mb-2">
                                        <span id="resume-current">0</span>
                                        <span class="text-lg text-white/70">of</span>
                                        <span id="resume-maximum">1000</span>
                                    </div>
                                    <div class="bg-white/20 rounded-full h-2">
                                        <div class="bg-white rounded-full h-2 transition-all duration-300" id="resume-progress-bar" style="width: 0%"></div>
                                    </div>
                                </div>
                                
                                <!-- Search Usage -->
                                <div class="bg-white/10 rounded-lg p-4 backdrop-blur-sm">
                                    <div class="flex items-center justify-between mb-2">
                                        <span class="text-sm font-medium">Search Queries</span>
                                        <span class="text-xs bg-white/20 px-2 py-1 rounded" id="search-usage-percent">0%</span>
                                    </div>
                                    <div class="flex items-center justify-between text-2xl font-bold mb-2">
                                        <span id="search-current">0</span>
                                        <span class="text-lg text-white/70">of</span>
                                        <span id="search-maximum">10000</span>
                                    </div>
                                    <div class="bg-white/20 rounded-full h-2">
                                        <div class="bg-white rounded-full h-2 transition-all duration-300" id="search-progress-bar" style="width: 0%"></div>
                                    </div>
                                </div>
                            </div>
                            <div class="mt-4 flex items-center justify-between">
                                <div class="text-sm">
                                    <span class="font-medium">Plan:</span> 
                                    <span class="bg-white/20 px-2 py-1 rounded text-xs uppercase" id="subscription-plan">Basic</span>
                                </div>
                                <div class="text-xs text-white/80">
                                    Last updated: <span id="last-updated">Just now</span>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Header Section -->
                    <div class="mb-6">
                        <div class="flex items-center justify-between">
                            <div>
                                <h2 class="text-2xl font-bold text-gray-900">My Recruitment Dashboard</h2>
                                <p class="mt-1 text-gray-600 text-sm">Track candidates and manage your recruitment pipeline</p>
                            </div>
                            <div class="flex items-center space-x-3">
                                <div class="text-sm text-gray-600">
                                    <i class="fas fa-calendar mr-1"></i>
                                    <span id="current-date"></span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Candidate Status Cards -->
                    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                        <!-- Card Example (repeat for each status) -->
                        <div role="button" tabindex="0" onclick="openCandidatesByStatus('selected')" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();openCandidatesByStatus('selected');}" class="cursor-pointer bg-white rounded-xl p-6 shadow-sm border border-gray-200 hover:shadow-md hover:border-emerald-300 hover:-translate-y-0.5 transition-all duration-200 flex flex-col items-center justify-center min-h-[180px]">
                            <div class="flex flex-col items-center mb-3">
                                <div class="w-14 h-14 flex items-center justify-center rounded-xl mb-2 bg-emerald-100">
                                    <i class="fas fa-check-circle text-emerald-600 text-2xl"></i>
                                </div>
                                <h3 class="text-3xl font-extrabold text-gray-900" id="selected-count"></h3>
                            </div>
                            <p class="text-gray-700 text-base font-semibold mb-1">Selected</p>
                            <p class="text-xs text-gray-500">Ready to hire</p>
                        </div>
                        <div role="button" tabindex="0" onclick="openCandidatesByStatus('rejected')" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();openCandidatesByStatus('rejected');}" class="cursor-pointer bg-white rounded-xl p-6 shadow-sm border border-gray-200 hover:shadow-md hover:border-red-300 hover:-translate-y-0.5 transition-all duration-200 flex flex-col items-center justify-center min-h-[180px]">
                            <div class="flex flex-col items-center mb-3">
                                <div class="w-14 h-14 flex items-center justify-center rounded-xl mb-2 bg-red-100">
                                    <i class="fas fa-times-circle text-red-600 text-2xl"></i>
                                </div>
                                <h3 class="text-3xl font-extrabold text-gray-900" id="rejected-count"></h3>
                            </div>
                            <p class="text-gray-700 text-base font-semibold mb-1">Rejected</p>
                            <p class="text-xs text-gray-500">This month</p>
                        </div>
                        <div role="button" tabindex="0" onclick="openCandidatesByStatus('shortlisted')" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();openCandidatesByStatus('shortlisted');}" class="cursor-pointer bg-white rounded-xl p-6 shadow-sm border border-gray-200 hover:shadow-md hover:border-yellow-300 hover:-translate-y-0.5 transition-all duration-200 flex flex-col items-center justify-center min-h-[180px]">
                            <div class="flex flex-col items-center mb-3">
                                <div class="w-14 h-14 flex items-center justify-center rounded-xl mb-2 bg-yellow-100">
                                    <i class="fas fa-star text-yellow-600 text-2xl"></i>
                                </div>
                                <h3 class="text-3xl font-extrabold text-gray-900" id="shortlisted-count"></h3>
                            </div>
                            <p class="text-gray-700 text-base font-semibold mb-1">Shortlisted</p>
                            <p class="text-xs text-gray-500">Awaiting review</p>
                        </div>
                        <div role="button" tabindex="0" onclick="openCandidatesByStatus('interviewed')" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();openCandidatesByStatus('interviewed');}" class="cursor-pointer bg-white rounded-xl p-6 shadow-sm border border-gray-200 hover:shadow-md hover:border-green-300 hover:-translate-y-0.5 transition-all duration-200 flex flex-col items-center justify-center min-h-[180px]">
                            <div class="flex flex-col items-center mb-3">
                                <div class="w-14 h-14 flex items-center justify-center rounded-xl mb-2 bg-green-100">
                                    <i class="fas fa-video text-green-600 text-2xl"></i>
                                </div>
                                <h3 class="text-3xl font-extrabold text-gray-900" id="interviewed-count"></h3>
                            </div>
                            <p class="text-gray-700 text-base font-semibold mb-1">Interviewed</p>
                            <p class="text-xs text-gray-500">Completed interviews</p>
                        </div>
                    </div>

                    <!-- Main Content Row -->
                    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
                        <!-- Search History Table -->
                        <div class="lg:col-span-2 bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                            <div class="flex items-center justify-between mb-6">
                                <div>
                                    <h3 class="text-lg font-semibold text-gray-900">Recent Resume Searches</h3>
                                    <p class="text-sm text-gray-600">Your latest search activities and results</p>
                                </div>
                                <div class="flex items-center space-x-2">
                                    <button onclick="refreshSearchHistory()" class="text-gray-400 hover:text-gray-600 p-2">
                                        <i class="fas fa-sync-alt"></i>
                                    </button>
                                    
                                </div>
                            </div>
                            
                            <!-- Search History Table -->
                            <div class="overflow-x-auto">
                                <table class="w-full">
                                    <thead>
                                        <tr class="border-b border-gray-200">
                                            <th class="text-left py-3 px-2 text-xs font-medium text-gray-500 uppercase tracking-wider">Search Query</th>
                                            <th class="text-left py-3 px-2 text-xs font-medium text-gray-500 uppercase tracking-wider">Results</th>
                                            <th class="text-left py-3 px-2 text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                                            <th class="text-left py-3 px-2 text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody id="search-history-table" class="divide-y divide-gray-100">
                                        <!-- Search history will be loaded here -->
                                    </tbody>
                                </table>
                            </div>
                            
                            <!-- Load More Button -->
                            <div class="mt-4 text-center">
                                <button onclick="loadPage('history')" class="px-4 py-2 text-gray-600 hover:text-gray-800 text-sm font-medium">
                                    View All Searches
                                </button>
                            </div>
                        </div>

                        <!-- Calendar & Schedule -->
                        <div class="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                            <div class="flex items-center justify-between mb-6">
                                <h3 class="text-lg font-semibold text-gray-900">📅 Schedule</h3>
                                <button type="button" onclick="openGeneralScheduleModal()" title="Add a new scheduled item" class="w-9 h-9 flex items-center justify-center rounded-lg text-gray-500 hover:text-white hover:bg-blue-600 transition-colors">
                                    <i class="fas fa-plus"></i>
                                </button>
                            </div>
                            
                            
                            
                            <!-- Upcoming Events -->
                            <div class="space-y-3">
                                <h4 class="text-sm font-medium text-gray-700">Upcoming Events</h4>
                                
                                <div id="upcoming-events">
                                    <!-- Events will be loaded dynamically -->
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Additional Dashboard Content Could Go Here -->
                </div>
            </div>
        `,
        searchResumes: `
            <div class="flex flex-col h-full relative bg-white overflow-hidden">
                <!-- Results Area (Initially Hidden) -->
                <div id="results-area" class="absolute inset-0 opacity-0 pointer-events-none transition-all duration-500">
                    <!-- Split View Container -->
                    <div class="split-view-container">
                        <!-- Left Panel - Candidate List -->
                        <div class="split-view-left">
                            <div class="split-view-header">
                                <h3 class="split-view-title">
                                    <i class="fas fa-users mr-2"></i>
                                    Candidates
                                </h3>
                                <div class="split-view-count" id="candidate-count">
                                    0 results
                                </div>
                            </div>
                            <div class="candidate-list" id="candidate-list">
                                <!-- Candidate list items will be displayed here -->
                            </div>
                        </div>
                        
                        <!-- Right Panel - Detailed View -->
                        <div class="split-view-right">
                            <div id="results-container">
                                <!-- Detailed candidate card will be displayed here -->
                                <div class="no-selection-message">
                                    <div class="no-selection-icon">
                                        <i class="fas fa-user-circle"></i>
                                    </div>
                                    <h3>Select a candidate</h3>
                                    <p>Choose a candidate from the list to view their detailed profile</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Main Search Interface -->
                <div id="chat-interface" class="flex flex-col items-center justify-start min-h-full px-6 py-8 overflow-y-auto transition-all duration-700 ease-in-out">
                    <!-- Header -->
                    <div class="text-center mb-8 mt-16">
                        <h1 class="text-3xl font-bold text-gray-900 mb-3">Find the perfect candidate with AI</h1>
                        <p class="text-gray-600 text-base max-w-2xl mx-auto">Describe your ideal candidate and let our AI search through thousands of resumes to find the best matches</p>
                    </div>

                    <!-- Search Input -->
                    <div class="w-full max-w-3xl mb-8">
                        <div class="relative">
                            <input type="text" id="chat-input" class="w-full px-6 py-4 text-base border border-gray-300 rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent shadow-sm" placeholder="Describe your ideal candidate or job requirements...">
                            <input type="file" id="jd-upload-input" accept=".pdf,.doc,.docx,.txt" class="hidden">
                            <div class="absolute right-3 top-1/2 transform -translate-y-1/2 flex items-center space-x-2">
                                <button id="jd-upload-button" type="button" title="Upload Job Description (PDF, DOCX, or TXT)" class="p-2 text-gray-400 hover:text-blue-600 transition-colors">
                                    <i class="fas fa-paperclip text-sm"></i>
                                </button>
                                <button id="send-button" class="p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                                    <i class="fas fa-paper-plane text-sm"></i>
                                </button>
                            </div>
                        </div>
                        <div id="jd-upload-status" class="hidden mt-2 text-xs text-gray-600"></div>
                    </div>

                    <!-- Search Options -->
                    <div class="w-full max-w-3xl mb-12">
                        <div class="flex items-center justify-center space-x-4 p-4 bg-gray-50 rounded-xl">
                            <div class="flex items-center space-x-2">
                                <i class="fas fa-search text-blue-600"></i>
                                <span class="text-sm font-medium text-gray-700">Search Results:</span>
                            </div>
                            <div class="flex items-center space-x-2">
                                <input type="number" id="result-count" min="1" max="100" value="10" class="w-20 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm" placeholder="10">
                                <span class="text-sm text-gray-700">results</span>
                            </div>
                            <div class="text-xs text-gray-500">
                                <i class="fas fa-info-circle mr-1"></i>
                                Consider increasing the number of searches if the expected resumes are not retrieved.
                            </div>
                        </div>
                    </div>

                    <!-- Search Categories -->
                    <div class="w-full max-w-5xl flex-1">
                        <div class="mb-6">
                            <h2 class="text-xl font-semibold text-gray-900">Find sample search prompts</h2>
                        </div>
                        
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                            <!-- Sample Job Description Card -->
                            <div class="search-category-card p-6 border border-gray-200 rounded-2xl hover:shadow-md transition-all duration-200 cursor-pointer col-span-3">
                                <div class="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center mb-4">
                                    <i class="fas fa-briefcase text-blue-600 text-lg"></i>
                                </div>
                                <h3 class="text-lg font-semibold text-gray-900 mb-2">Sample Job Description</h3>
                                <p class="text-gray-600 text-sm leading-relaxed mb-2">
                                    <strong>Senior Full Stack Developer (React & Node.js)</strong><br/>
                                    <span class="block mt-1">We are seeking a highly skilled Senior Full Stack Developer with 5+ years of experience in building scalable web applications. The ideal candidate will have deep expertise in React, Node.js, RESTful APIs, and cloud platforms (AWS or GCP). Responsibilities include designing and developing new features, collaborating with cross-functional teams, and ensuring high performance and responsiveness of applications. Experience with CI/CD, Docker, and modern DevOps practices is a plus.</span>
                                    <br/>
                                    <strong>Key Skills:</strong> React, Node.js, JavaScript/TypeScript, REST APIs, SQL/NoSQL, AWS/GCP, Docker, CI/CD, Agile
                                </p>
                                <p class="text-gray-500 text-xs mt-2">Tip: Use this sample as a starting point for your search or customize it for your specific role.</p>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Fixed Bottom Chat Input (Initially Hidden) -->
                <div id="bottom-chat-container" class="absolute bottom-0 left-0 right-0 bg-white border-t border-gray-200 p-4 opacity-0 pointer-events-none transition-all duration-500">
                    <div class="max-w-4xl mx-auto">
                        <div class="relative">
                            <input type="text" id="bottom-chat-input" class="w-full px-4 py-3 pr-12 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm" placeholder="Ask another question or refine your search...">
                            <button id="bottom-send-button" class="absolute right-2 top-1/2 transform -translate-y-1/2 p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                                <i class="fas fa-paper-plane text-xs"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `,
        history: `
            <div class="p-4 h-full overflow-y-auto bg-gray-50">
                <div class="max-w-6xl mx-auto">
                    <div class="mb-6">
                        <div class="flex items-center justify-between">
                            <div>
                                <h2 class="text-lg font-bold heading-gradient">Search Reports</h2>
                                <p class="mt-1 text-gray-600 text-xs">Review and re-run your previous searches</p>
                            </div>
                            <div class="flex items-center space-x-3">
                                <div class="relative">
                                    <input type="text" id="history-search" placeholder="Search history..." 
                                           class="w-64 px-3 py-2 pl-10 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                                    <i class="fas fa-search absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 text-sm"></i>
                                </div>
                                <button id="clear-history" class="px-3 py-2 text-gray-600 hover:text-red-600 text-sm border border-gray-300 rounded-lg hover:border-red-300 transition-colors">
                                    <i class="fas fa-trash mr-1"></i>Clear All
                                </button>
                            </div>
                        </div>
                    </div>
                    
                    <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                        <!-- Table Header -->
                        <div class="bg-gray-50 border-b border-gray-200 px-6 py-3">
                            <div class="grid grid-cols-12 gap-4 items-center text-xs font-medium text-gray-600 uppercase tracking-wide">
                                <div class="col-span-4">Job Description</div>
                                <div class="col-span-2">Date & Time</div>
                                <div class="col-span-2">Candidates</div>
                                <div class="col-span-3">Top Results</div>
                                <div class="col-span-1 text-center">Actions</div>
                            </div>
                        </div>
                        
                        <!-- Table Body -->
                        <div id="history-table-body" class="divide-y divide-gray-200">
                        </div>
                        <!-- Pagination Footer -->
                        <div id="history-pagination" class="hidden px-6 py-3 border-t border-gray-200 bg-gray-50 flex items-center justify-between text-sm text-gray-600">
                        </div>
                    </div>
                </div>
            </div>
        `,
        uploadFiles: `
            <div class="p-4 h-full overflow-y-auto bg-gray-50">
                <div class="max-w-4xl mx-auto">
                    <!-- Header Section -->
                    <div class="mb-6">
                        <h2 class="text-2xl font-bold text-gray-900">Upload Resume Files</h2>
                        <p class="mt-1 text-gray-600 text-sm">Upload resume files for your company. Files will be stored securely and only accessible to your organization.</p>
                    </div>

                    <!-- Upload Stats -->
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                        <div class="bg-white rounded-xl p-4 shadow-sm border border-gray-200">
                            <div class="flex items-center">
                                <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center mr-3">
                                    <i class="fas fa-file-upload text-blue-600"></i>
                                </div>
                                <div>
                                    <p class="text-lg font-bold text-gray-900" id="total-uploaded">0</p>
                                    <p class="text-sm text-gray-600">Files Uploaded Today</p>
                                </div>
                            </div>
                        </div>
                        <div class="bg-white rounded-xl p-4 shadow-sm border border-gray-200">
                            <div class="flex items-center">
                                <div class="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center mr-3">
                                    <i class="fas fa-check-circle text-green-600"></i>
                                </div>
                                <div>
                                    <p class="text-lg font-bold text-gray-900" id="successful-uploads">0</p>
                                    <p class="text-sm text-gray-600">Successful Uploads</p>
                                </div>
                            </div>
                        </div>
                        <div class="bg-white rounded-xl p-4 shadow-sm border border-gray-200">
                            <div class="flex items-center">
                                <div class="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center mr-3">
                                    <i class="fas fa-exclamation-triangle text-red-600"></i>
                                </div>
                                <div>
                                    <p class="text-lg font-bold text-gray-900" id="failed-uploads">0</p>
                                    <p class="text-sm text-gray-600">Failed Uploads</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Upload Options -->
                    <div class="bg-white rounded-xl p-6 shadow-sm border border-gray-200 mb-6">
                        <div class="mb-6">
                            <h3 class="text-lg font-semibold text-gray-900 mb-4">Upload Options</h3>
                            <div class="flex space-x-4">
                                <button id="file-upload-tab" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium">
                                    <i class="fas fa-file-upload mr-2"></i>File Upload
                                </button>
                                <button id="email-scrape-tab" class="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors font-medium">
                                    <i class="fas fa-envelope mr-2"></i>Email Scraping
                                </button>
                            </div>
                        </div>

                        <!-- File Upload Section -->
                        <div id="file-upload-section" class="text-center">
                            <div id="drop-zone" class="border-2 border-dashed border-gray-300 rounded-lg p-8 hover:border-blue-400 transition-colors cursor-pointer">
                                <div class="flex flex-col items-center">
                                    <div class="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mb-4">
                                        <i class="fas fa-cloud-upload-alt text-blue-600 text-2xl"></i>
                                    </div>
                                    <h3 class="text-lg font-semibold text-gray-900 mb-2">Drop files here or click to browse</h3>
                                    <p class="text-gray-600 text-sm mb-4">Support for PDF, DOC, DOCX files (max 10MB per file, 100MB per batch)</p>
                                    <button id="browse-files" class="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium">
                                        <i class="fas fa-folder-open mr-2"></i>Browse Files
                                    </button>
                                    <input type="file" id="file-input" multiple accept=".pdf,.doc,.docx" class="hidden">
                                </div>
                            </div>
                        </div>

                        <!-- Email Scraping Section -->
                        <div id="email-scrape-section" class="hidden">
                            <div class="max-w-2xl mx-auto">
                                <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
                                    <div class="flex items-center">
                                        <i class="fas fa-info-circle text-yellow-600 mr-2"></i>
                                        <span class="text-sm text-yellow-800">
                                            <strong>Email Scraping:</strong> This feature will scan your email for resume attachments and interview-related documents. Your credentials are used only for this session and are not stored.
                                        </span>
                                    </div>
                                </div>

                                <div class="space-y-4">
                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">Email Provider</label>
                                        <select id="email-provider" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                                            <option value="">Select Email Provider</option>
                                            <option value="gmail">Gmail</option>
                                            <option value="outlook">Outlook 365</option>
                                        </select>
                                    </div>

                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">Email Address</label>
                                        <input type="email" id="email-address" placeholder="your.email@company.com" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                                    </div>

                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">Email Password</label>
                                        <div class="relative">
                                            <input type="password" id="email-password" placeholder="Your email password or app password" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 pr-10">
                                            <button type="button" id="toggle-password" class="absolute inset-y-0 right-0 pr-3 flex items-center">
                                                <i class="fas fa-eye text-gray-400 hover:text-gray-600"></i>
                                            </button>
                                        </div>
                                        <p class="text-xs text-gray-500 mt-1">For Gmail, use an <a href="https://support.google.com/accounts/answer/185833" target="_blank" class="text-blue-600 hover:underline">App Password</a> instead of your regular password</p>
                                    </div>

                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">Email Limit</label>
                                        <input type="number" id="email-limit" value="100" min="1" max="1000" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                                        <p class="text-xs text-gray-500 mt-1">Maximum number of recent emails to scan (default: 100)</p>
                                    </div>

                                    <button id="start-email-scrape" class="w-full px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium disabled:bg-gray-400 disabled:cursor-not-allowed">
                                        <i class="fas fa-envelope-open-text mr-2"></i>Start Email Scraping
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Batch Configuration -->
                    <div class="bg-white rounded-xl p-6 shadow-sm border border-gray-200 mb-6">
                        <div class="flex items-center justify-between mb-4">
                            <h3 class="text-lg font-semibold text-gray-900">
                                <i class="fas fa-layer-group mr-2 text-blue-600"></i>
                                Smart Batch Upload
                            </h3>
                        </div>
                        
                        <div class="text-sm text-gray-600">
                            Files are automatically organized into batches under 32MB each for reliable upload.
                        </div>
                    </div>

                    <!-- Hidden Configuration Panel -->
                    <div class="hidden">
                        <input type="text" id="bucket-name" value="">
                        <input type="text" id="upload-folder" value="">
                        <input type="checkbox" id="auto-process" checked>
                    </div>

                    <!-- Upload Queue -->
                    <div class="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                        <div class="flex items-center justify-between mb-4">
                            <h3 class="text-lg font-semibold text-gray-900">Upload Queue</h3>
                            <div class="flex space-x-2">
                                <button id="clear-queue" class="px-3 py-1 text-gray-600 hover:text-gray-800 text-sm">Clear All</button>
                                <button id="start-upload" class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm font-medium disabled:bg-gray-400 disabled:cursor-not-allowed" disabled>
                                    <i class="fas fa-play mr-2"></i>Start Upload
                                </button>
                            </div>
                        </div>

                        <!-- Overall Progress Bar -->
                        <div id="overall-progress-container" class="hidden mb-4">
                            <div class="flex items-center justify-between mb-2">
                                <span class="text-sm font-medium text-gray-700">Overall Progress</span>
                                <span id="overall-progress-text" class="text-sm text-gray-600">0%</span>
                            </div>
                            <div class="w-full bg-gray-200 rounded-full h-3">
                                <div id="overall-progress-bar" class="bg-blue-600 h-3 rounded-full transition-all duration-500" style="width: 0%"></div>
                            </div>
                            <div class="flex items-center justify-between mt-2 text-xs text-gray-500">
                                <span id="batch-progress-text">Batch 0/0</span>
                                <span id="files-progress-text">0/0 files completed</span>
                            </div>
                        </div>

                        <div id="upload-queue" class="space-y-3">
                            <div class="text-center text-gray-500 py-8">
                                <i class="fas fa-inbox text-4xl text-gray-300 mb-2"></i>
                                <p>No files selected. Drop files or browse to add them to the queue.</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `,
        jdBuilder: `
            <div class="p-4 h-full overflow-y-auto bg-gray-50">
                <div class="max-w-7xl mx-auto">
                    <!-- Main Content -->
                    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        <!-- Left Panel - Input Form -->
                        <div class="lg:col-span-1 space-y-6">
                            <!-- Job Basic Info -->
                            <div class="bg-white rounded-lg shadow p-6">
                                <h3 class="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                                    <i class="fas fa-briefcase text-blue-500 mr-2"></i>
                                    Job Information
                                </h3>
                                <div class="space-y-4">
                                <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">Job Title *</label>
                                        <input type="text" id="jd-job-title" placeholder="e.g., Senior Software Engineer" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                                    </div>
                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">Company Name</label>
                                        <input type="text" id="jd-company-name" placeholder="e.g., Acme Corp" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                                    </div>
                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">Company Details</label>
                                        <textarea id="jd-company-details" rows="3" placeholder="Brief company description, mission, values, culture, or any specific information about the company you'd like to include..." class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"></textarea>
                                    </div>
                                    
                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">Department</label>
                                        <input type="text" id="jd-department" placeholder="e.g., Engineering" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                                    </div>
                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">Location</label>
                                        <input type="text" id="jd-location" placeholder="e.g., San Francisco, CA / Remote" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                                    </div>
                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">Experience Level</label>
                                        <select id="jd-experience-level" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                                            <option value="">Select Level</option>
                                            <option value="entry">Entry Level (0-2 years)</option>
                                            <option value="mid">Mid Level (3-5 years)</option>
                                            <option value="senior">Senior Level (6-10 years)</option>
                                            <option value="lead">Lead/Principal (10+ years)</option>
                                            <option value="executive">Executive</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">Employment Type</label>
                                        <select id="jd-employment-type" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                                            <option value="full-time">Full-time</option>
                                            <option value="part-time">Part-time</option>
                                            <option value="contract">Contract</option>
                                            <option value="temporary">Temporary</option>
                                            <option value="internship">Internship</option>
                                        </select>
                                    </div>
                                </div>
                            </div>

                            <!-- AI Assistant -->
                            <div class="bg-white rounded-lg shadow p-6">

                                <div class="space-y-4">
                                    <div>
                                        <label class="block text-sm font-medium text-gray-700 mb-2">
                                            Describe the role or paste existing content
                                        </label>
                                        <textarea id="jd-ai-input" rows="4" placeholder="Describe what kind of person you're looking for, key responsibilities, or paste an existing job description to improve..." class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"></textarea>
                                    </div>

                                </div>
                            </div>

                            <!-- Skills -->
                            <div class="bg-white rounded-lg shadow p-6">
                                <h3 class="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                                    <i class="fas fa-tags text-green-500 mr-2"></i>
                                    Required Skills
                                </h3>
                                <div class="space-y-4">
                                    <div>
                                        <input type="text" id="jd-skill-input" placeholder="Add a skill and press Enter" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500">
                                    </div>
                                    <div id="jd-skills-list" class="flex flex-wrap gap-2 min-h-[40px] p-3 border border-gray-200 rounded-lg bg-gray-50">
                                        <span class="text-gray-500 text-sm">Skills will appear here...</span>
                                    </div>

                                </div>
                            </div>
                            <button id="jd-generate-btn" class="w-full bg-gradient-to-r from-purple-600 to-purple-700 text-white px-4 py-3 rounded-lg hover:from-purple-700 hover:to-purple-800 transition-all duration-200 shadow-lg text-lg font-semibold">
                                <i class="fas fa-magic mr-2"></i>Generate with AI
                            </button>
                        </div>

                        <!-- Right Panel - Generated JD Preview -->
                        <div class="lg:col-span-2">
                            <div class="bg-white rounded-lg shadow p-6 h-full">
                                <div class="flex justify-between items-center mb-4">
                                    <h3 class="text-lg font-semibold text-gray-800 flex items-center">
                                        <i class="fas fa-file-contract text-indigo-500 mr-2"></i>
                                        Job Description Preview
                                    </h3>
                                    <div class="flex space-x-2">
                                        <button id="jd-copy-btn" class="bg-gray-100 text-gray-700 px-3 py-1 rounded-lg hover:bg-gray-200 transition-colors text-sm">
                                            <i class="fas fa-copy mr-1"></i>Copy
                                        </button>
                                        <button id="jd-download-btn" class="bg-green-100 text-green-700 px-3 py-1 rounded-lg hover:bg-green-200 transition-colors text-sm">
                                            <i class="fas fa-download mr-1"></i>Download
                                        </button>
                                        
                                    </div>
                                </div>
                                
                                <div id="jd-preview" class="min-h-[600px] border border-gray-200 rounded-lg p-6 bg-white focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500" contenteditable="true" style="line-height: 1.6;">
                                    <div class="text-center text-gray-500 mt-20">
                                        <i class="fas fa-file-contract text-4xl mb-4"></i>
                                        <p class="text-lg">Your job description will appear here</p>
                                        <p class="text-sm">Fill in the job information and use AI to generate content</p>
                                    </div>
                                </div>
                                
                                <div id="jd-progress" class="hidden mt-4">
                                    <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
                                        <div class="flex items-center">
                                            <i class="fas fa-spinner fa-spin text-blue-500 mr-3"></i>
                                            <div>
                                                <p class="text-blue-800 font-medium">Generating Job Description...</p>
                                                <p class="text-blue-600 text-sm" id="jd-progress-text">Processing your requirements</p>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>


                </div>
            </div>
        `,
        settings: `
            <div class="p-4 h-full overflow-y-auto bg-gray-50">
                <div class="max-w-4xl mx-auto">
                    <div class="mb-6">
                        <h2 class="text-2xl font-bold text-gray-900">Settings & User Management</h2>
                        <p class="mt-1 text-gray-600 text-sm">Manage your preferences and users</p>
                    </div>
                    
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <!-- User Management Section (Tenant Admin Only) -->
                        <div id="user-management-section" class="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                            <div class="flex items-center justify-between mb-4">
                                <div>
                                    <h3 class="text-lg font-semibold text-gray-900">User Management</h3>
                                    <p class="text-sm text-gray-600">Manage users in your organization</p>
                                </div>
                                <button id="add-user-btn" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium">
                                    <i class="fas fa-plus mr-2"></i>Add User
                                </button>
                            </div>
                            
                            <!-- Users List -->
                            <div id="users-list" class="space-y-3">
                                <div class="text-center text-gray-500 py-4">
                                    <i class="fas fa-users text-2xl text-gray-300 mb-2"></i>
                                    <p class="text-sm">Loading users...</p>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Company Information -->
                        <div id="company-info-section" class="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                            <h3 class="text-lg font-semibold text-gray-900 mb-4">Company Information</h3>
                            <div id="company-details" class="space-y-3">
                                <div class="text-center text-gray-500 py-4">
                                    <i class="fas fa-building text-2xl text-gray-300 mb-2"></i>
                                    <p class="text-sm">Loading company information...</p>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Account Settings -->
                        <div class="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                            <h3 class="text-lg font-semibold text-gray-900 mb-4">Account Settings</h3>
                            <div class="space-y-4">
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">Display Name</label>
                                    <input type="text" id="display-name" class="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-700" placeholder="Your display name" readonly>
                                </div>
                                <div>
                                    <label class="block text-sm font-medium text-gray-700 mb-2">Email Address</label>
                                    <input type="email" id="email-address" class="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-700" placeholder="your.email@company.com" readonly>
                                </div>
                                <p class="text-xs text-gray-500">
                                    <i class="fas fa-info-circle mr-1"></i>
                                    Contact your administrator to change your name or email.
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `
    };

    // Make loadPage available globally
    window.loadPage = function (page) {
        const mainContent = document.getElementById('main-content');
        if (!mainContent) {
            console.error('Main content element not found');
            return;
        }

        mainContent.innerHTML = pages[page];

        // Update page title and description
        const titles = {
            dashboard: { title: 'Dashboard', desc: 'Overview & Analytics' },
            searchResumes: { title: 'Search Resumes', desc: 'Find the perfect candidates with AI assistance' },
            jdBuilder: { title: 'JD Builder', desc: 'Create professional job descriptions with AI assistance' },
            vectorSearch: { title: 'Vector Search Test', desc: 'Test the Google Cloud vector store directly' },
            history: { title: 'Search History', desc: 'Review and re-run your previous searches' },
            uploadFiles: { title: 'Upload Files', desc: 'Upload resume files to Google Cloud Storage' },
            settings: { title: 'Settings', desc: 'Customize your preferences' }
        };

        // document.getElementById('page-title').innerText = titles[page].title;
        // document.querySelector('#page-title + p').innerText = titles[page].desc;

        if (page === 'searchResumes') {
            // Add small delay to ensure DOM is ready
            setTimeout(() => {
                initializeSearchPage();
            }, 10);
        } else if (page === 'jdBuilder') {
            initializeJDBuilderPage();
        } else if (page === 'vectorSearch') {
            // Add small delay to ensure DOM is ready
            setTimeout(() => {
                initializeVectorSearchPage();
            }, 10);
        } else if (page === 'history') {
            initializeHistoryPage();
        } else if (page === 'dashboard') {
            initializeDashboard();
        } else if (page === 'uploadFiles') {
            initializeUploadPage();
        } else if (page === 'settings') {
            initializeSettingsPage();
        }
    }

    function initializeSearchPage() {
        // Ensure the bottom chat container is visible when navigating to search page normally
        const bottomChatContainer = document.getElementById('bottom-chat-container');
        if (bottomChatContainer) {
            bottomChatContainer.style.display = '';
        }

        const chatInput = document.getElementById('chat-input');
        const sendButton = document.getElementById('send-button');
        const bottomChatInput = document.getElementById('bottom-chat-input');
        const bottomSendButton = document.getElementById('bottom-send-button');
        const categoryCards = document.querySelectorAll('.search-category-card');

        // Handle category card clicks
        console.log('Found category cards:', categoryCards.length); // Debug log
        categoryCards.forEach(card => {
            card.addEventListener('click', () => {
                const cardTitle = card.querySelector('h3').textContent;
                console.log('Category card clicked:', cardTitle); // Debug log
                let searchQuery = '';

                switch (cardTitle) {
                    case 'Technical Roles':
                        searchQuery = 'Find developers, engineers, and technical specialists with specific programming languages and frameworks';
                        break;
                    case 'Creative Positions':
                        searchQuery = 'Discover designers, writers, and creative professionals with portfolio experience and design skills';
                        break;
                    case 'Management & Leadership':
                        searchQuery = 'Search for managers, directors, and leaders with team management and strategic planning experience';
                        break;
                    case 'Sample Job Description':
                        searchQuery = 'Senior Full Stack Developer (React & Node.js) - We are seeking a highly skilled Senior Full Stack Developer with 5+ years of experience in building scalable web applications. The ideal candidate will have deep expertise in React, Node.js, RESTful APIs, and cloud platforms (AWS or GCP). Key Skills: React, Node.js, JavaScript/TypeScript, REST APIs, SQL/NoSQL, AWS/GCP, Docker, CI/CD, Agile';
                        break;
                }

                console.log('Search query set to:', searchQuery); // Debug log
                if (searchQuery) {
                    chatInput.value = searchQuery;
                    handleSendMessage();
                } else {
                    console.error('No search query generated for card:', cardTitle);
                }
            });
        });

        // Handle main send button click
        sendButton.addEventListener('click', handleSendMessage);

        // Handle bottom send button click
        bottomSendButton.addEventListener('click', handleBottomSendMessage);

        // Handle enter key press for both inputs
        chatInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                handleSendMessage();
            }
        });

        bottomChatInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                handleBottomSendMessage();
            }
        });

        // Add validation for result count input
        const resultCountInput = document.getElementById('result-count');
        if (resultCountInput) {
            resultCountInput.addEventListener('change', (e) => {
                let value = parseInt(e.target.value);
                if (isNaN(value) || value < 1) {
                    e.target.value = 1;
                } else if (value > 100) {
                    e.target.value = 100;
                }
            });
        }

        // Wire JD-upload (paperclip) button -> hidden file input -> backend parser
        const jdUploadBtn = document.getElementById('jd-upload-button');
        const jdUploadInput = document.getElementById('jd-upload-input');
        const jdUploadStatus = document.getElementById('jd-upload-status');
        if (jdUploadBtn && jdUploadInput) {
            jdUploadBtn.addEventListener('click', (e) => {
                e.preventDefault();
                jdUploadInput.click();
            });
            jdUploadInput.addEventListener('change', async (e) => {
                const file = e.target.files && e.target.files[0];
                if (!file) return;
                const maxBytes = 10 * 1024 * 1024;
                if (file.size > maxBytes) {
                    if (jdUploadStatus) {
                        jdUploadStatus.classList.remove('hidden');
                        jdUploadStatus.classList.add('text-red-600');
                        jdUploadStatus.textContent = 'File too large (max 10 MB).';
                    }
                    jdUploadInput.value = '';
                    return;
                }
                if (jdUploadStatus) {
                    jdUploadStatus.classList.remove('hidden', 'text-red-600');
                    jdUploadStatus.classList.add('text-gray-600');
                    jdUploadStatus.textContent = 'Reading "' + file.name + '"...';
                }
                try {
                    const fd = new FormData();
                    fd.append('file', file);
                    const resp = await fetch('/api/parse-jd-file', { method: 'POST', body: fd });
                    if (!resp.ok) {
                        let msg = 'Failed to read file (' + resp.status + ').';
                        try {
                            const j = await resp.json();
                            if (j && j.detail) msg = j.detail;
                        } catch (_) { }
                        throw new Error(msg);
                    }
                    const data = await resp.json();
                    const text = (data && data.text) ? String(data.text).trim() : '';
                    if (!text) {
                        throw new Error('No text could be extracted from the file.');
                    }
                    if (chatInput) {
                        chatInput.value = text;
                        chatInput.focus();
                    }
                    if (jdUploadStatus) {
                        jdUploadStatus.classList.remove('text-red-600');
                        jdUploadStatus.classList.add('text-green-600');
                        jdUploadStatus.textContent = 'Loaded "' + file.name + '" (' + text.length + ' chars). You can edit before searching.';
                    }
                } catch (err) {
                    console.error('JD upload failed:', err);
                    if (jdUploadStatus) {
                        jdUploadStatus.classList.remove('hidden', 'text-green-600', 'text-gray-600');
                        jdUploadStatus.classList.add('text-red-600');
                        jdUploadStatus.textContent = err && err.message ? err.message : 'Upload failed.';
                    }
                } finally {
                    jdUploadInput.value = '';
                }
            });
        }
    }

    function handleSendMessage() {
        const chatInput = document.getElementById('chat-input');
        const message = chatInput.value.trim();

        if (message) {

            // Show the bottom chat container for new searches
            const bottomChatContainer = document.getElementById('bottom-chat-container');
            if (bottomChatContainer) {
                bottomChatContainer.style.display = '';
            }

            // Animate chat interface away
            animateChatToResults();

            // Show results area
            setTimeout(() => {
                const resultsArea = document.getElementById('results-area');
                resultsArea.classList.remove('opacity-0', 'pointer-events-none');
                resultsArea.classList.add('opacity-100');

                // Add user message
                addUserMessage(message);

                // Show loading
                showLoadingMessage();



                // Try real search first
                performRealSearch(message)
                    .then(data => {
                        hideLoadingMessage();

                        // Check if we have valid data (including empty results array)
                        if (data && Array.isArray(data.results)) {
                            console.log('Search completed successfully:', {
                                totalResults: data.results.length,
                                searchStrategy: data.search_strategy,
                                hasHRScorecards: !!data.hr_scorecards
                            });



                            // Generate enhanced results (this updates the DOM directly)
                            generateEnhancedResults(data);

                            // Save search to history with HR scorecard data
                            const topCandidates = data.results.slice(0, 5).map(r => ({
                                name: r.gemini_analysis?.hr_scorecard?.candidate_overview?.name ||
                                    r.gemini_analysis?.analysis_json?.candidate_name ||
                                    'Unknown',
                                score: r.gemini_analysis?.match_score || 0
                            }));
                            saveSearchToHistory(message, data.results.length, topCandidates);


                        } else {
                            console.error('Invalid search response data:', data);
                            throw new Error('Invalid search response data');
                        }

                        // Ensure proper scrolling after results are added
                        setTimeout(() => {
                            resultsArea.scrollTop = resultsArea.scrollHeight;
                        }, 100);
                    })
                    .catch(error => {
                        console.error('Search failed:', error);
                        hideLoadingMessage();



                        // Show proper error message instead of mock results
                        const resultsContainerDiv = document.getElementById('results-container');
                        resultsContainerDiv.innerHTML = `
                            <div class="flex items-center justify-center h-full min-h-[400px]">
                                <div class="text-center max-w-md mx-auto p-8">
                                    <div class="w-20 h-20 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
                                        <i class="fas fa-exclamation-triangle text-red-500 text-2xl"></i>
                                    </div>
                                    <h3 class="text-xl font-semibold text-gray-800 mb-4">
                                        ${error.message && error.message.includes('maximum search limit') ? 'Search Limit Reached' : 'Oops! Something went wrong'}
                                    </h3>
                                    <p class="text-gray-600 mb-6 leading-relaxed">
                                        ${error.message && error.message.includes('maximum search limit') ? error.message : 'We encountered an issue while searching for candidates. Our technical team has been notified and will resolve this shortly.'}
                                    </p>
                                    <div class="space-y-3">
                                        <button onclick="location.reload()" class="w-full bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition-colors">
                                            <i class="fas fa-refresh mr-2"></i>
                                            Try Again
                                        </button>
                                        <p class="text-sm text-gray-500">
                                            <i class="fas fa-info-circle mr-1"></i>
                                            If the problem persists, our support team will be in touch.
                                        </p>
                                    </div>
                                </div>
                            </div>
                        `;

                        // Log error details for debugging
                        console.error('Search error details:', {
                            message: error.message,
                            stack: error.stack,
                            query: message,
                            timestamp: new Date().toISOString()
                        });
                    });

            }, 300);

            chatInput.value = '';
        }
    }

    function handleBottomSendMessage() {
        const bottomChatInput = document.getElementById('bottom-chat-input');
        const message = bottomChatInput.value.trim();
        if (message) {

            // Ensure the bottom chat container is visible for new searches
            const bottomChatContainer = document.getElementById('bottom-chat-container');
            if (bottomChatContainer) {
                bottomChatContainer.style.display = '';
            }
            bottomChatInput.value = '';
            addUserMessage(message);
            showLoadingMessage();



            // Try real search first
            performRealSearch(message)
                .then(data => {
                    hideLoadingMessage();

                    // Check if we have valid data (including empty results array)
                    if (data && Array.isArray(data.results)) {
                        console.log('Bottom search completed successfully:', {
                            totalResults: data.results.length,
                            searchStrategy: data.search_strategy,
                            hasHRScorecards: !!data.hr_scorecards
                        });



                        // Generate enhanced results (this updates the DOM directly)
                        generateEnhancedResults(data);

                        // Save search to history with HR scorecard data
                        const topCandidates = data.results.slice(0, 5).map(r => ({
                            name: r.gemini_analysis?.hr_scorecard?.candidate_overview?.name ||
                                r.gemini_analysis?.analysis_json?.candidate_name ||
                                'Unknown',
                            score: r.gemini_analysis?.match_score || 0
                        }));
                        saveSearchToHistory(message, data.results.length, topCandidates);
                    } else {
                        console.error('Invalid bottom search response data:', data);
                        throw new Error('Invalid search response data');
                    }

                    // Ensure proper scrolling after results are added
                    const resultsScrollArea = document.getElementById('results-area');
                    setTimeout(() => {
                        if (resultsScrollArea) {
                            resultsScrollArea.scrollTop = resultsScrollArea.scrollHeight;
                        }
                    }, 100);
                })
                .catch(error => {
                    console.error('Search failed:', error);
                    hideLoadingMessage();



                    // Show proper error message instead of mock results
                    const resultsArea = document.getElementById('results-container');
                    resultsArea.innerHTML = `
                        <div class="flex items-center justify-center h-full min-h-[400px]">
                            <div class="text-center max-w-md mx-auto p-8">
                                <div class="w-20 h-20 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
                                    <i class="fas fa-exclamation-triangle text-red-500 text-2xl"></i>
                                </div>
                                <h3 class="text-xl font-semibold text-gray-800 mb-4">
                                    ${error.message && error.message.includes('maximum search limit') ? 'Search Limit Reached' : 'Oops! Something went wrong'}
                                </h3>
                                <p class="text-gray-600 mb-6 leading-relaxed">
                                    ${error.message && error.message.includes('maximum search limit') ? error.message : 'We encountered an issue while searching for candidates. Our technical team has been notified and will resolve this shortly.'}
                                </p>
                                <div class="space-y-3">
                                    <button onclick="location.reload()" class="w-full bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition-colors">
                                        <i class="fas fa-refresh mr-2"></i>
                                        Try Again
                                    </button>
                                    <p class="text-sm text-gray-500">
                                        <i class="fas fa-info-circle mr-1"></i>
                                        If the problem persists, our support team will be in touch.
                                    </p>
                                </div>
                            </div>
                        </div>
                    `;

                    // Log error details for debugging
                    console.error('Search error details:', {
                        message: error.message,
                        stack: error.stack,
                        query: message,
                        timestamp: new Date().toISOString()
                    });
                });
        }
    }

    // Make animateChatToResults available globally
    window.animateChatToResults = function () {
        const chatInterface = document.getElementById('chat-interface');
        const bottomChatContainer = document.getElementById('bottom-chat-container');
        const resultsArea = document.getElementById('results-area');

        // Fade out main interface
        if (chatInterface) {
            chatInterface.style.opacity = '0';
            chatInterface.style.transform = 'translateY(-20px)';

            // Show results area and bottom chat container
            setTimeout(() => {
                chatInterface.style.display = 'none';

                // Show results area
                if (resultsArea) {
                    resultsArea.classList.remove('opacity-0', 'pointer-events-none');
                    resultsArea.classList.add('opacity-100');
                }

                // Show bottom chat container
                if (bottomChatContainer) {
                    bottomChatContainer.classList.remove('opacity-0', 'pointer-events-none');
                    bottomChatContainer.classList.add('opacity-100');
                }

                // Ensure results area can scroll properly with bottom chat visible
                ensureProperScrolling();
            }, 300);
        }
    }

    // Make ensureProperScrolling available globally
    window.ensureProperScrolling = function () {
        const resultsArea = document.getElementById('results-area');
        const bottomChatContainer = document.getElementById('bottom-chat-container');

        if (resultsArea && bottomChatContainer) {
            // Adjust scroll position to account for bottom chat
            setTimeout(() => {
                resultsArea.scrollTop = resultsArea.scrollHeight;
            }, 100);
        }
    }

    // Make addUserMessage available globally
    window.addUserMessage = function (message) {
        // In split view, we don't show user messages in the results area
        // The query is already visible in the search interface
    }

    // Make showLoadingMessage available globally
    window.showLoadingMessage = function () {
        // Show loading in the candidate list
        const candidateList = document.getElementById('candidate-list');
        if (candidateList) {
            candidateList.innerHTML = `
                <div class="text-center py-8">
                    <div class="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                        <i class="fas fa-spinner fa-spin text-blue-600 text-lg"></i>
                    </div>
                    <div id="search-progress-step" class="text-gray-600 text-sm">Searching for candidates...</div>
                    <div id="search-progress-detail" class="text-gray-500 text-xs mt-2">Analyzing resumes with AI</div>
                    <div class="w-full max-w-xs mx-auto mt-3 bg-gray-200 rounded-full h-1.5 overflow-hidden">
                        <div id="search-progress-bar" class="bg-blue-500 h-1.5 rounded-full transition-all duration-300" style="width:0%"></div>
                    </div>
                </div>
            `;
        }

        // Show loading in results container
        const resultsContainer = document.getElementById('results-container');
        if (resultsContainer) {
            resultsContainer.innerHTML = `
                <div class="flex items-center justify-center h-full">
                    <div class="text-center">
                        <div class="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                            <i class="fas fa-search text-gray-400 text-2xl"></i>
                        </div>
                        <h3 id="search-progress-title" class="text-lg font-medium text-gray-600 mb-2">Searching candidates...</h3>
                        <p id="search-progress-subtitle" class="text-sm text-gray-500">Please wait while we analyze the resumes</p>
                    </div>
                </div>
            `;
        }
    }

    // Update the progress UI from a task-status payload.
    window.updateSearchProgress = function (status) {
        try {
            const progress = (status && status.progress) || {};
            const step = progress.step || status.status || '';
            const cur = progress.current_candidate;
            const total = progress.total_candidates;
            const pct = (typeof progress.progress_percent === 'number')
                ? progress.progress_percent
                : (cur && total ? Math.round(cur / total * 100) : 0);
            const cacheHits = progress.cache_hits || 0;

            const stepLabels = {
                'extracting_keywords': 'Extracting keywords from job description-',
                'optimizing_query':    'Optimizing search query-',
                'searching_candidates':'Searching candidate database-',
                'generating_scorecards': total
                    ? `Analyzing candidate ${cur || 0} / ${total} (${pct}%)-`
                    : 'Analyzing candidates-',
                'saving_results':      'Saving results-',
                'completed':           'Done.',
            };
            const label = stepLabels[step] || (step ? `${step}-` : 'Working-');

            const stepEl    = document.getElementById('search-progress-step');
            const detailEl  = document.getElementById('search-progress-detail');
            const barEl     = document.getElementById('search-progress-bar');
            const titleEl   = document.getElementById('search-progress-title');
            const subEl     = document.getElementById('search-progress-subtitle');
            if (stepEl)   stepEl.textContent = label;
            if (titleEl)  titleEl.textContent = label;
            if (detailEl) detailEl.textContent = cacheHits
                ? `${cacheHits} reused from cache`
                : 'Powered by Vertex AI Search + Gemini';
            if (subEl)    subEl.textContent   = detailEl ? detailEl.textContent : '';
            if (barEl && pct >= 0) barEl.style.width = Math.max(2, Math.min(100, pct)) + '%';
        } catch (e) {
            console.warn('updateSearchProgress error', e);
        }
    }

    function showRealTimeProgress() {
        // In split view, we don't show real-time progress
        // The loading indicators in the split panels are sufficient
    }

    function addRealTimeProgressLine(message, type = 'info', step = null, total = null) {
        const progressLines = document.getElementById('progress-lines');
        if (!progressLines) return;

        const line = document.createElement('div');
        line.classList.add('flex', 'items-center', 'py-1', 'fade-in');

        // Type-based styling
        const typeColors = {
            'info': { bg: 'bg-blue-100', text: 'text-blue-600', dot: 'bg-blue-500', icon: 'fas fa-info-circle' },
            'success': { bg: 'bg-green-100', text: 'text-green-600', dot: 'bg-green-500', icon: 'fas fa-check-circle' },
            'warning': { bg: 'bg-yellow-100', text: 'text-yellow-600', dot: 'bg-yellow-500', icon: 'fas fa-exclamation-triangle' },
            'error': { bg: 'bg-red-100', text: 'text-red-600', dot: 'bg-red-500', icon: 'fas fa-times-circle' }
        };

        const colors = typeColors[type] || typeColors['info'];

        // Add timestamp
        const timestamp = new Date().toLocaleTimeString('en-US', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });

        const stepInfo = step && total ? ` (${step}/${total})` : '';

        line.innerHTML = `
            <div class="w-3 h-3 ${colors.bg} rounded-full flex items-center justify-center mr-2">
                <i class="${colors.icon} ${colors.text} text-xs"></i>
            </div>
            <span class="text-gray-700 flex-1">${message}</span>
            <div class="flex items-center space-x-2 ml-2">
                ${stepInfo ? `<span class="text-xs text-gray-500">${stepInfo}</span>` : ''}
                <span class="text-xs text-gray-400">${timestamp}</span>
                <div class="w-2 h-2 ${colors.dot} rounded-full animate-pulse"></div>
            </div>
        `;
        progressLines.appendChild(line);

        // Auto-scroll to bottom
        progressLines.scrollTop = progressLines.scrollHeight;

        // Also scroll the main results area
        const resultsArea = document.getElementById('results-area');
        if (resultsArea) {
            resultsArea.scrollTop = resultsArea.scrollHeight;
        }
    }

    // Make hideLoadingMessage available globally
    window.hideLoadingMessage = function () {
        // In split view, loading is handled by the generateEnhancedResults function
        // No need to hide loading messages as they are replaced by actual content
    }

    // Make showFinalResultsNotification available globally
    window.showFinalResultsNotification = function () {
        // In split view, we don't need a separate notification
        // The results are displayed immediately in the split panels
    }

    // Function to extract job title from search query
    function extractJobTitleFromQuery(query) {
        if (!query || typeof query !== 'string') {
            return 'Position';
        }

        const lowerQuery = query.toLowerCase();

        // Common job title patterns
        const titlePatterns = [
            // Direct matches
            /(?:looking for|seeking|hiring|need|want)\s+(?:a\s+|an\s+)?([^.;,]+?)(?:\s+with|\s+having|\s+who|\s+that|$)/i,
            /(?:position|role|job)(?:\s+of|\s+for)?\s*:?\s*([^.;,]+?)(?:\s+with|\s+having|\s+who|\s+that|$)/i,
            /([a-zA-Z\s]+?)\s+(?:developer|engineer|analyst|manager|specialist|coordinator|director|lead|senior|junior|intern)/i,
            /(senior|junior|lead|principal|staff)\s+([a-zA-Z\s]+?)(?:\s+with|\s+having|\s+who|\s+that|$)/i,
            /([a-zA-Z\s]+?)\s+(?:with|having)\s+\d+\+?\s*years/i,

            // Common job titles
            /(data scientist|software engineer|full stack developer|backend developer|frontend developer|devops engineer|product manager|business analyst|machine learning engineer|ai engineer|cloud architect|technical lead|scrum master|qa engineer|mobile developer|web developer|ui\/ux designer|systems administrator|network engineer|database administrator|security analyst|project manager)/i
        ];

        // Try to match patterns
        for (const pattern of titlePatterns) {
            const match = query.match(pattern);
            if (match) {
                let title = match[1] || match[0];
                if (match[2]) title = `${match[1]} ${match[2]}`;

                // Clean up the title
                title = title.trim()
                    .replace(/\s+/g, ' ')
                    .replace(/^(a |an |the )/i, '')
                    .replace(/\s+(with|having|who|that).*$/i, '');

                if (title.length > 3 && title.length < 50) {
                    return title.split(' ').map(word =>
                        word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
                    ).join(' ');
                }
            }
        }

        // Fallback: Look for common keywords and infer title
        const roleKeywords = {
            'python': 'Python Developer',
            'java': 'Java Developer',
            'react': 'React Developer',
            'node': 'Node.js Developer',
            'angular': 'Angular Developer',
            'vue': 'Vue.js Developer',
            'machine learning': 'Machine Learning Engineer',
            'data science': 'Data Scientist',
            'devops': 'DevOps Engineer',
            'cloud': 'Cloud Engineer',
            'aws': 'Cloud Engineer',
            'azure': 'Cloud Engineer',
            'gcp': 'Cloud Engineer',
            'frontend': 'Frontend Developer',
            'backend': 'Backend Developer',
            'fullstack': 'Full Stack Developer',
            'qa': 'QA Engineer',
            'testing': 'QA Engineer',
            'mobile': 'Mobile Developer',
            'android': 'Android Developer',
            'ios': 'iOS Developer',
            'product management': 'Product Manager',
            'business analysis': 'Business Analyst',
            'ui': 'UI/UX Designer',
            'ux': 'UI/UX Designer'
        };

        for (const [keyword, title] of Object.entries(roleKeywords)) {
            if (lowerQuery.includes(keyword)) {
                return title;
            }
        }

        // Final fallback
        return 'Position';
    }

    function performRealSearch(query) {
        const formData = new FormData();
        formData.append('query', query);

        // Get the result count from the number input
        const resultCountInput = document.getElementById('result-count');
        // Default to 10 if the input is empty or not a valid number
        let resultCount = 10;
        if (resultCountInput && resultCountInput.value) {
            const inputValue = parseInt(resultCountInput.value);
            if (!isNaN(inputValue) && inputValue > 0) {
                resultCount = inputValue;
            }
        }
        formData.append('result_count', resultCount.toString());

        // Extract job title from query for enhanced analysis
        const jobTitle = extractJobTitleFromQuery(query);
        formData.append('job_title', jobTitle);

        // Use HR scorecard search with keyword analysis (instead of smart-search-stream)
        return fetch('/api/hr-scorecard-search', {
            method: 'POST',
            body: formData
        })
            .then(async response => {
                if (!response.ok) {
                    const errorData = await response.json();
                    const errorMessage = errorData.detail || 'Search failed';

                    // Show specific error for search limits
                    if (errorMessage.includes('maximum search limit')) {
                        throw new Error(errorMessage);
                    } else {
                        throw new Error('Search failed');
                    }
                }

                // Handle regular JSON response (not streaming)
                return response.json();
            })
            .then(data => {
                // If backend submitted a Cloud Task, poll until completed
                // and then fetch results.
                if (data && data.task_id && (data.status === 'pending' || data.success === true) && !Array.isArray(data.results)) {
                    console.log('HR Scorecard task submitted, polling status:', data.task_id);
                    return pollHRScorecardTask(data.task_id);
                }

                // Legacy/synchronous path
                console.log('HR Scorecard search response:', data);
                return {
                    results: data.results || [],
                    total_results: data.total_results || 0,
                    query: data.query || '',
                    job_title: data.job_title || 'Position',
                    search_strategy: data.search_strategy || 'hr_scorecard_comprehensive',
                    hr_scorecards: data.hr_scorecards || [],
                    hr_metrics: data.hr_metrics || {},
                    standardized_keywords: data.standardized_keywords || {},
                    enhanced_search: true,
                    all_analyses: data.all_analyses || [],
                    analyzed_count: data.analyzed_count || 0,
                    top_result_analysis: data.top_result_analysis || null,
                    top_scorecard: data.top_scorecard || null
                };
            });
    }

    // Poll an HR-scorecard Cloud Task until it completes (or fails / times out)
    // and return the normalized results payload from the task-results endpoint.
    function pollHRScorecardTask(taskId, opts) {
        opts = opts || {};
        // Adaptive backoff: poll quickly at first so a fast search returns
        // immediately, then ramp up to avoid hammering the backend on long
        // searches. Caller may still pass `intervalMs` to override.
        const fixedIntervalMs = opts.intervalMs;
        const backoffSchedule = [800, 1200, 1800, 2500, 3500, 4000];
        const maxIntervalMs = 4000;
        const timeoutMs = opts.timeoutMs || 10 * 60 * 1000;
        const startedAt = Date.now();
        let pollCount = 0;

        function delay(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

        function nextDelay() {
            if (fixedIntervalMs) return fixedIntervalMs;
            const idx = Math.min(pollCount, backoffSchedule.length - 1);
            pollCount += 1;
            return backoffSchedule[idx] || maxIntervalMs;
        }

        function fetchStatus() {
            return fetch('/api/hr-scorecard-task-status/' + encodeURIComponent(taskId), {
                method: 'GET', credentials: 'same-origin'
            }).then(function (r) {
                if (!r.ok) throw new Error('Task status check failed (' + r.status + ')');
                return r.json();
            });
        }

        function fetchResults() {
            return fetch('/api/hr-scorecard-task-results/' + encodeURIComponent(taskId), {
                method: 'GET', credentials: 'same-origin'
            }).then(function (r) {
                if (!r.ok) throw new Error('Task results fetch failed (' + r.status + ')');
                return r.json();
            });
        }

        function loop() {
            return fetchStatus().then(function (status) {
                const s = status && status.status;
                console.log('HR Scorecard task status:', s, status && status.progress);
                try { if (window.updateSearchProgress) window.updateSearchProgress(status); } catch (e) {}

                if (s === 'completed') {
                    return fetchResults().then(function (data) {
                        return {
                            results: data.results || [],
                            total_results: data.total_results || (data.results ? data.results.length : 0),
                            query: data.query || '',
                            job_title: data.job_title || 'Position',
                            search_strategy: data.search_strategy || 'hr_scorecard_comprehensive',
                            hr_scorecards: data.hr_scorecards || [],
                            hr_metrics: data.hr_metrics || {},
                            standardized_keywords: data.standardized_keywords || {},
                            enhanced_search: true,
                            all_analyses: data.all_analyses || [],
                            analyzed_count: data.analyzed_count || 0,
                            top_result_analysis: data.top_result_analysis || null,
                            top_scorecard: data.top_scorecard || null,
                            task_id: taskId
                        };
                    });
                }

                if (s === 'failed') {
                    const msg = (status && (status.error_message || (status.progress && status.progress.error))) || 'Task failed';
                    throw new Error(msg);
                }

                if (Date.now() - startedAt > timeoutMs) {
                    throw new Error('Search is taking too long. Please try again.');
                }

                return delay(nextDelay()).then(loop);
            });
        }

        return loop();
    }

    // Make generateEnhancedResults available globally
    window.generateEnhancedResults = function (data) {
        // Store the data globally for split view
        window.searchResultsData = data;

        // Debug logging
        console.log('generateEnhancedResults called with data:', data);
        console.log('Total results received:', data.results ? data.results.length : 0);

        // Show all results with analysis data (improved filtering)
        // For HR scorecard searches, be more permissive since they might have different structure
        const isHRScorecard = data.search_strategy === 'hr_scorecard_comprehensive' ||
            data.hr_scorecards ||
            (data.results && data.results.length > 0 && data.results[0].analysis_type);

        console.log('Search type detection:', {
            isHRScorecard: isHRScorecard,
            searchStrategy: data.search_strategy,
            hasHRScorecards: !!data.hr_scorecards,
            firstResultAnalysisType: data.results && data.results.length > 0 ? data.results[0].analysis_type : null
        });

        const highScoreResults = data.results.filter(result => {
            // For HR scorecard searches, accept all results that have gemini_analysis
            if (isHRScorecard) {
                const hasGeminiAnalysis = !!result.gemini_analysis;
                console.log('HR Scorecard result check:', {
                    hasGeminiAnalysis: hasGeminiAnalysis,
                    analysisType: result.analysis_type,
                    documentName: result.document_name
                });
                return hasGeminiAnalysis;
            }

            // For other searches, use the original logic
            const hasAnalysis = result.gemini_analysis ||
                result.analysis ||
                result.hr_scorecard ||
                result.match_score !== undefined;

            console.log('Standard result analysis check:', {
                hasGeminiAnalysis: !!result.gemini_analysis,
                geminiSuccess: result.gemini_analysis ? result.gemini_analysis.success : false,
                hasAnalysis: !!result.analysis,
                hasHrScorecard: !!result.hr_scorecard,
                hasMatchScore: result.match_score !== undefined,
                finalDecision: hasAnalysis
            });

            return hasAnalysis;
        });

        // Update candidate count
        const candidateCount = document.getElementById('candidate-count');
        if (candidateCount) {
            candidateCount.textContent = `${highScoreResults.length} results`;
        }

        // Inject "Export All" button into the split-view header (idempotent).
        try {
            const headerEl = candidateCount ? candidateCount.closest('.split-view-header') : null;
            if (headerEl && !headerEl.querySelector('#export-all-btn') && highScoreResults.length > 0) {
                const btn = document.createElement('button');
                btn.id = 'export-all-btn';
                btn.type = 'button';
                btn.title = 'Export all candidates as a single PDF';
                btn.innerHTML = '<i class="fas fa-file-export mr-1"></i> Export All';
                btn.style.cssText = 'margin-left:8px;padding:4px 10px;border-radius:6px;background:#4f46e5;color:#fff;font-size:12px;font-weight:600;border:0;cursor:pointer;';
                btn.onmouseover = function () { btn.style.background = '#4338ca'; };
                btn.onmouseout = function () { btn.style.background = '#4f46e5'; };
                btn.onclick = function () { exportAllCandidatesReport(); };
                headerEl.appendChild(btn);
            } else if (headerEl) {
                const existing = headerEl.querySelector('#export-all-btn');
                if (existing) existing.style.display = highScoreResults.length > 0 ? '' : 'none';
            }
        } catch (e) {
            console.warn('Could not inject Export All button:', e);
        }

        // Inject "Only matches" toggle + criteria hint based on whether any
        // candidate carries a criteria_match block.
        try {
            const anyCriteria = (highScoreResults || []).some(c => c && c.criteria_match && c.criteria_match.evaluated);
            const anyMisses = (highScoreResults || []).some(c => c && c.criteria_match && (c.criteria_match.misses || []).length > 0);
            const headerEl2 = document.getElementById('candidate-list-header')
                || document.querySelector('.candidate-list-header')
                || document.querySelector('#results-container .results-header');
            if (headerEl2 && anyCriteria && !headerEl2.querySelector('#criteria-only-toggle')) {
                const tog = document.createElement('label');
                tog.id = 'criteria-only-toggle';
                tog.title = 'Hide candidates missing any required criterion';
                tog.style.cssText = 'margin-left:8px;display:inline-flex;align-items:center;gap:4px;font-size:12px;color:#374151;cursor:pointer;user-select:none;';
                tog.innerHTML = '<input type="checkbox" id="criteria-only-toggle-cb" style="margin:0;"> Only matches';
                tog.querySelector('input').addEventListener('change', (e) => {
                    const list = document.getElementById('candidate-list');
                    if (list) list.classList.toggle('hide-misses', e.target.checked);
                });
                headerEl2.appendChild(tog);
                if (!anyMisses) tog.style.opacity = '0.5';
            }
            // Hint when query had no detectable hard criteria.
            const noCriteria = !anyCriteria && (highScoreResults || []).length > 0;
            const listParent = document.getElementById('candidate-list')?.parentElement;
            if (listParent && noCriteria && !listParent.querySelector('#criteria-hint')) {
                const hint = document.createElement('div');
                hint.id = 'criteria-hint';
                hint.style.cssText = 'font-size:11px;color:#6b7280;margin:4px 0 8px;font-style:italic;';
                hint.textContent = 'Tip: add hard filters like "5+ years", "speaks French", or "based in Dubai" to narrow results.';
                listParent.insertBefore(hint, listParent.firstChild);
            }
        } catch (e) {
            console.warn('Could not inject criteria UI:', e);
        }

        // Clear and populate candidate list
        const candidateList = document.getElementById('candidate-list');
        if (candidateList) {
            candidateList.innerHTML = '';

            // Create list items for each candidate
            highScoreResults.forEach((candidate, index) => {
                const analysis = candidate.gemini_analysis;
                const analysisData = analysis.hr_scorecard || analysis.analysis_json;
                const score = analysis.match_score || 0;

                // Extract candidate info
                const candidateName = extractCandidateName(candidate, analysisData, index);
                const candidateRole = analysisData?.candidate_overview?.position_applied_for || 'Position';
                const candidateLocation = analysisData?.candidate_overview?.location || 'Not specified';
                const matchStatus = getMatchStatus(score);
                const esc = window.escapeHtml || ((value) => {
                    const div = document.createElement('div');
                    div.textContent = value == null ? '' : String(value);
                    return div.innerHTML;
                });
                const safeScore = (window.safeNumber || ((value) => Number(value) || 0))(score, 0, 0, 100);
                const safeStatusClass = String(matchStatus || '')
                    .toLowerCase()
                    .replace(/[^a-z0-9_-]+/g, '-')
                    .replace(/^-+|-+$/g, '') || 'status';

                // Create list item
                const listItem = document.createElement('div');
                listItem.className = 'candidate-list-item';
                listItem.dataset.candidateIndex = index;
                const cmHere = candidate && candidate.criteria_match;
                if (cmHere && cmHere.evaluated && (cmHere.misses || []).length > 0) {
                    listItem.dataset.hasMisses = '1';
                }
                listItem.innerHTML = `
                    <div class="candidate-list-avatar">
                        ${esc(candidateName.charAt(0).toUpperCase())}
                    </div>
                    <div class="candidate-list-info">
                        <div class="candidate-list-name">${esc(candidateName)}</div>
                        <div class="candidate-list-role">${esc(candidateRole)}</div>
                        <div class="candidate-list-location">
                            <i class="fas fa-map-marker-alt"></i>
                            ${esc(candidateLocation)}
                        </div>
                        ${renderCriteriaBadges(candidate)}
                    </div>
                    <div class="candidate-list-score">
                        <div class="candidate-list-score-value">${safeScore}%</div>
                        <div class="candidate-list-score-status ${safeStatusClass}">${esc(matchStatus)}</div>
                    </div>
                `;

                // Add click event
                listItem.addEventListener('click', () => {
                    selectCandidate(index, highScoreResults);
                });

                candidateList.appendChild(listItem);
            });

            // Auto-select first candidate
            if (highScoreResults.length > 0) {
                selectCandidate(0, highScoreResults);
            }
        }

        // Show message if no high-scoring candidates found
        if (highScoreResults.length === 0) {
            console.warn('No qualifying candidates found. Debug info:', {
                totalResults: data.results ? data.results.length : 0,
                sampleResult: data.results && data.results.length > 0 ? data.results[0] : null,
                dataKeys: data.results && data.results.length > 0 ? Object.keys(data.results[0]) : [],
                isHRScorecard: isHRScorecard
            });

            const resultsContainer = document.getElementById('results-container');
            if (resultsContainer) {
                // For HR scorecard with no results, check if we have unprocessed candidates
                if (isHRScorecard && data.results && data.results.length > 0) {
                    // Try to show the first result anyway, even if filtering failed
                    console.log('Attempting to show first result despite filter failure');
                    selectCandidate(0, data.results);
                } else {
                    // Show no results message with specific handling for empty datastore
                    const isEmptyDatastore = data.empty_datastore || (data.total_results === 0 && data.message && data.message.includes('upload resumes'));
                    const iconClass = isEmptyDatastore ? 'fas fa-upload text-blue-600' : 'fas fa-search text-yellow-600';
                    const bgColor = isEmptyDatastore ? 'bg-blue-50 border-blue-200' : 'bg-yellow-50 border-yellow-200';
                    const textColor = isEmptyDatastore ? 'text-blue-800' : 'text-yellow-800';
                    const messageColor = isEmptyDatastore ? 'text-blue-700' : 'text-yellow-700';
                    const actionColor = isEmptyDatastore ? 'text-blue-600' : 'text-yellow-600';

                    resultsContainer.innerHTML = `
                        <div class="${bgColor} border rounded-xl p-6 text-center fade-in-up">
                            <div class="w-16 h-16 ${isEmptyDatastore ? 'bg-blue-100' : 'bg-yellow-100'} rounded-full flex items-center justify-center mx-auto mb-4">
                                <i class="${iconClass} text-2xl"></i>
                            </div>
                            <h3 class="text-lg font-semibold ${textColor} mb-2">
                                ${isEmptyDatastore ? 'No Resumes Uploaded' : 'No Candidates Found'}
                            </h3>
                            <p class="${messageColor} text-sm mb-4">
                                ${isEmptyDatastore
                            ? (data.message || 'No resumes have been uploaded to your company datastore yet.')
                            : (data.results && data.results.length > 0
                                ? `We found ${data.results.length} candidates but could not process their analysis.`
                                : 'No resumes found matching your search criteria.')}
                            </p>
                            <p class="${actionColor} text-xs">
                                ${isEmptyDatastore
                            ? 'Go to the Upload page to add resumes to your datastore.'
                            : 'Try refining your search query or upload more resumes.'}
                            </p>
                            ${isEmptyDatastore ? `
                                <div class="mt-4">
                                    <a href="/" class="inline-flex items-center px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors">
                                        <i class="fas fa-upload mr-2"></i>
                                        Upload Resumes
                                    </a>
                                </div>
                            ` : ''}
                        </div>
                    `;
                }
            }
            return;
        }
    }

    // Helper function to extract candidate name
    function extractCandidateName(candidate, analysisData, index) {
        function safeExtractCandidateData(data, field, fallback = 'Not available') {
            if (!data || !data.candidate_overview) {
                return fallback;
            }

            const value = data.candidate_overview[field];

            // Prevent job description content from appearing by checking for common JD phrases
            if (typeof value === 'string') {
                const jdIndicators = [
                    'we are looking for',
                    'ideal candidate',
                    'responsibilities',
                    'requirements',
                    'qualifications',
                    'job description',
                    'position summary',
                    'what we offer'
                ];

                const lowerValue = value.toLowerCase();
                const hasJDContent = jdIndicators.some(indicator => lowerValue.includes(indicator));
                const isTooLong = value.length > 200;

                if (hasJDContent || isTooLong) {
                    return fallback;
                }
            }

            return value || fallback;
        }

        const candidateName = safeExtractCandidateData(analysisData, 'name', `Candidate ${index + 1}`);

        // Additional validation
        let finalCandidateName = candidateName;
        if (candidateName.toLowerCase().includes('we are looking') ||
            candidateName.toLowerCase().includes('ideal candidate') ||
            candidateName.length > 100) {
            // Try to extract name from filename if available
            if (candidate.file_path) {
                const fileName = candidate.file_path.split('/').pop().replace(/\.[^/.]+$/, "");
                finalCandidateName = fileName.replace(/[_-]/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            } else {
                finalCandidateName = `Candidate ${index + 1}`;
            }
        }

        return finalCandidateName;
    }

    // Helper function to get match status
    // Make getMatchStatus available globally
    window.getMatchStatus = function (score) {
        return score >= 80 ? 'Strong Fit' : score >= 60 ? 'Medium Fit' : 'Weak Fit';
    }

    // Render small green/red badges showing which user-specified hard
    // criteria (years of experience, languages, location) the candidate
    // matched. Returns '' if the search had no hard criteria.
    window.renderCriteriaBadges = function (candidate) {
        const cm = candidate && candidate.criteria_match;
        if (!cm || !cm.evaluated) return '';
        const esc = window.escapeHtml || ((v) => {
            const d = document.createElement('div'); d.textContent = v == null ? '' : String(v); return d.innerHTML;
        });
        const items = [];
        for (const m of (cm.matches || [])) {
            items.push(`<span class="criteria-badge criteria-badge-match" title="matches required ${esc(m.criterion)}">✓ ${esc(m.required)}</span>`);
        }
        for (const m of (cm.misses || [])) {
            const pen = (m && typeof m.penalty === 'number') ? m.penalty : 25;
            items.push(`<span class="criteria-badge criteria-badge-miss" title="missing required ${esc(m.criterion)} (-${pen} score)">✗ ${esc(m.required)}</span>`);
        }
        if (!items.length) return '';
        return `<div class="criteria-badges">${items.join('')}</div>`;
    };
    const renderCriteriaBadges = window.renderCriteriaBadges;

    // Function to select a candidate and show their details
    // Make selectCandidate available globally
    window.selectCandidate = function (index, highScoreResults) {
        // Update active state in list
        const allListItems = document.querySelectorAll('.candidate-list-item');
        allListItems.forEach(item => item.classList.remove('active'));

        const selectedItem = document.querySelector(`[data-candidate-index="${index}"]`);
        if (selectedItem) {
            selectedItem.classList.add('active');
        }

        // Generate and display detailed card
        const candidate = highScoreResults[index];
        generateDetailedCandidateCard(candidate, index);
    }

    // Function to generate detailed candidate card
    // Make generateDetailedCandidateCard available globally
    window.generateDetailedCandidateCard = function (candidate, index) {
        const resultsContainer = document.getElementById('results-container');
        if (!resultsContainer) return;

        try {
            console.log('generateDetailedCandidateCard called for candidate:', candidate);

            // Improved analysis data extraction with more debugging
            const analysis = candidate.gemini_analysis || candidate.analysis || candidate;
            const analysisData = analysis.hr_scorecard ||
                analysis.analysis_json ||
                analysis.scorecard ||
                candidate.hr_scorecard ||
                analysis;
            const score = analysis.match_score ||
                analysisData?.candidate_overview?.overall_match_score ||
                candidate.match_score ||
                0;

            console.log('Extracted analysis data:', {
                analysis: !!analysis,
                analysisData: !!analysisData,
                score: score,
                candidateName: analysisData?.candidate_overview?.name,
                analysisDataKeys: analysisData ? Object.keys(analysisData) : [],
                analysisDataStructure: analysisData
            });

            // Validate we have minimum required data
            if (!analysisData || typeof analysisData !== 'object') {
                console.error('Invalid analysisData structure:', analysisData);
                throw new Error('Invalid analysis data structure');
            }

            // Clear container
            resultsContainer.innerHTML = '';

            // Create card
            const card = document.createElement('div');
            card.classList.add('professional-resume-card');

            // Store analysis data in data attributes for the export function
            card.setAttribute('data-analysis-data', JSON.stringify(analysisData));
            card.setAttribute('data-candidate-index', index);

            // Helper function to safely extract candidate data
            function safeExtractCandidateData(data, field, fallback = 'Not available') {
                if (!data || !data.candidate_overview) {
                    return fallback;
                }

                const value = data.candidate_overview[field];

                // Prevent job description content from appearing by checking for common JD phrases
                if (typeof value === 'string') {
                    const jdIndicators = [
                        'we are looking for',
                        'ideal candidate',
                        'responsibilities',
                        'requirements',
                        'qualifications',
                        'job description',
                        'position summary',
                        'what we offer'
                    ];

                    const lowerValue = value.toLowerCase();
                    const hasJDContent = jdIndicators.some(indicator => lowerValue.includes(indicator));
                    const isTooLong = value.length > 200;

                    if (hasJDContent || isTooLong) {
                        return fallback;
                    }
                }

                return value || fallback;
            }

            // Extract candidate info with additional safety
            let candidateName, candidatePhone, candidateEmail, candidateLocation, candidateRole, experienceYears;

            try {
                candidateName = safeExtractCandidateData(analysisData, 'name', `Candidate ${index + 1}`);
                candidatePhone = safeExtractCandidateData(analysisData, 'phone', 'Not available');
                candidateEmail = safeExtractCandidateData(analysisData, 'email', 'Not available');
                candidateLocation = safeExtractCandidateData(analysisData, 'location', 'Not specified');
                candidateRole = safeExtractCandidateData(analysisData, 'position_applied_for', 'Position');
                experienceYears = safeExtractCandidateData(analysisData, 'experience_years', 'Not specified');
            } catch (e) {
                console.error('Error extracting candidate data:', e);
                candidateName = `Candidate ${index + 1}`;
                candidatePhone = 'Not available';
                candidateEmail = 'Not available';
                candidateLocation = 'Not specified';
                candidateRole = 'Position';
                experienceYears = 'Not specified';
            }

            // Additional validation
            let finalCandidateName = candidateName;
            if (candidateName.toLowerCase().includes('we are looking') ||
                candidateName.toLowerCase().includes('ideal candidate') ||
                candidateName.length > 100) {
                if (candidate.file_path) {
                    const fileName = candidate.file_path.split('/').pop().replace(/\.[^/.]+$/, "");
                    finalCandidateName = fileName.replace(/[_-]/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                } else {
                    finalCandidateName = `Candidate ${index + 1}`;
                }
            }

            // Extract HR scorecard data with backward compatibility and safety
            let scoreBreakdown, keywordCoverage, careerTimeline, tenurePrediction;
            let analysisSummary, aiSummary, resumeHighlights;

            try {
                scoreBreakdown = analysisData?.score_breakdown || {};
                keywordCoverage = analysisData?.keyword_coverage || {};
                careerTimeline = analysisData?.career_timeline || [];
                tenurePrediction = analysisData?.tenure_prediction || {};

                // career_timeline may arrive as a string in older / migrated
                // payloads; force it to an array so .slice().map() is safe.
                if (!Array.isArray(careerTimeline)) {
                    if (careerTimeline && typeof careerTimeline === 'object') {
                        careerTimeline = Object.values(careerTimeline);
                    } else {
                        careerTimeline = [];
                    }
                }

                // Handle both new and old structures for analysis summary
                analysisSummary = analysisData?.analysis_summary || {};
                aiSummary = analysisSummary.ai_analysis || analysisData?.ai_summary || 'No AI analysis available';

                // Ensure resumeHighlights is always an array
                resumeHighlights = [];
                if (analysisSummary.resume_highlights && Array.isArray(analysisSummary.resume_highlights)) {
                    resumeHighlights = analysisSummary.resume_highlights;
                } else if (analysisData?.resume_snippets && Array.isArray(analysisData.resume_snippets)) {
                    resumeHighlights = analysisData.resume_snippets;
                }


            } catch (e) {
                console.error('Error extracting HR scorecard data:', e);
                scoreBreakdown = {};
                keywordCoverage = {};
                careerTimeline = [];
                tenurePrediction = {};
                analysisSummary = {};
                aiSummary = 'No AI analysis available';
                resumeHighlights = [];

            }

            // Create the match status text
            const matchStatus = analysisData?.candidate_overview?.match_status ||
                (score >= 80 ? 'Strong Fit' : score >= 60 ? 'Medium Fit' : 'Weak Fit');

            // Add search result ID as data attribute if available
            if (candidate.id) {
                card.setAttribute('data-search-result-id', candidate.id);
            }

            // Final safety check and debug logging
            console.log('About to create HTML template with:', {
                finalCandidateName,
                candidateRole,
                candidateLocation,
                candidateEmail,
                candidatePhone,
                experienceYears,
                score,
                matchStatus,
                aiSummary: aiSummary ? aiSummary.substring(0, 100) + '...' : 'None',
                resumeHighlights: resumeHighlights.length
            });

            const esc = window.escapeHtml || ((value) => {
                const div = document.createElement('div');
                div.textContent = value == null ? '' : String(value);
                return div.innerHTML;
            });
            const safeNum = window.safeNumber || ((value, fallback = 0, min = 0, max = 100) => {
                const number = Number(value);
                return Number.isFinite(number) ? Math.min(max, Math.max(min, number)) : fallback;
            });
            const safeClassName = (value) => String(value || '')
                .toLowerCase()
                .replace(/[^a-z0-9_-]+/g, '-')
                .replace(/^-+|-+$/g, '') || 'item';
            const safeScore = safeNum(score, 0, 0, 100);
            const safeEmailValue = String(candidateEmail || '').trim();
            const canEmailCandidate = /^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$/.test(safeEmailValue);
            const candidateFilePath = candidate.file_path || '';
            card.dataset.candidateName = finalCandidateName;

            try {
                card.innerHTML = `
                <!-- Professional Header -->
                <div class="professional-card-header">
                    <div class="professional-header-content">
                        <div class="professional-candidate-avatar">
                            ${esc(finalCandidateName.charAt(0).toUpperCase())}
                        </div>
                        <div class="professional-candidate-info">
                            <h1>${esc(finalCandidateName)}</h1>
                            <div class="professional-candidate-role">${esc(candidateRole)}</div>
                            <div class="professional-candidate-location">
                                <i class="fas fa-map-marker-alt"></i>
                                ${esc(candidateLocation)} &bull; ${esc(experienceYears)} experience
                            </div>
                            <div class="professional-contact-info">
                                <div class="professional-contact-item">
                                    <i class="fas fa-envelope"></i>
                                    ${esc(candidateEmail)}
                                </div>
                                <div class="professional-contact-item">
                                    <i class="fas fa-phone"></i>
                                    ${esc(candidatePhone)}
                                </div>
                            </div>
                        </div>
                        <div class="professional-match-score">
                            <div class="professional-score-circle" style="--score-deg: ${safeScore * 3.6}deg;">
                                <div class="professional-score-text">${safeScore}%</div>
                            </div>
                            <div class="professional-match-status">${esc(matchStatus)}</div>
                        </div>
                    </div>
                </div>

                <!-- Professional Card Body -->
                <div class="professional-card-body">
                    <!-- AI Analysis Section -->
                    <div class="professional-section">
                        <h2 class="professional-section-title">
                            <i class="fas fa-brain"></i>
                            AI Analysis
                        </h2>
                        
                        <div class="professional-ai-summary">
                            <!-- AI Analysis Content -->
                            <div class="analysis-content">
                                <p>${esc(aiSummary)}</p>
                            </div>

                            <!-- Resume Highlights -->
                            ${resumeHighlights.length > 0 ? `
                            <div class="analysis-content">
                                <h4 class="analysis-subtitle">Resume Highlights</h4>
                                <ul class="analysis-highlights-list">
                                    ${resumeHighlights.slice(0, 3).map((highlight, snippetIndex) => {
                    // Handle both string and object formats
                    const highlightText = typeof highlight === 'string' ? highlight : (highlight.text || highlight.snippet || 'No highlight available');
                    return `<li class="analysis-highlight-item">${esc(highlightText)}</li>`;
                }).join('')}
                                </ul>
                            </div>
                            ` : ''}


                        </div>
                    </div>

                    ${Object.keys(scoreBreakdown).length > 0 ? `
                    <!-- Detailed Score Analysis -->
                    <div class="professional-section">
                        <h2 class="professional-section-title">
                            <i class="fas fa-chart-line"></i>
                            Detailed Score Analysis
                        </h2>
                        <div class="professional-score-grid">
                            ${Object.entries(scoreBreakdown).filter(([key, data]) => {
                    // Hide specific sections from frontend display
                    const hiddenSections = [
                        'experience_level_fit',
                        'keyword_technical_match',
                        'final_scoring_summary'
                    ];
                    return !hiddenSections.includes(key.toLowerCase());
                }).map(([key, data]) => {
                    const skillName = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                    const scoreValue = safeNum(data.score || 0, 0, 0, 100);
                    const comment = data.comment || 'No detailed analysis available';
                    return `
                                <div class="professional-score-item ${safeClassName(key)}">
                                    <div class="professional-score-header">
                                        <div class="professional-score-name">${esc(skillName)}</div>
                                        <div class="professional-score-value">${scoreValue}%</div>
                                    </div>
                                    <div class="professional-score-bar">
                                        <div class="professional-score-fill" style="width: ${scoreValue}%; animation-delay: ${Math.random() * 0.5}s;"></div>
                                    </div>
                                    <div class="professional-score-comment">${esc(comment)}</div>
                                </div>
                                `;
                }).join('')}
                        </div>
                    </div>
                    ` : ''}

                    ${careerTimeline.length > 0 ? `
                    <!-- Career Timeline -->
                    <div class="professional-section">
                        <h2 class="professional-section-title">
                            <i class="fas fa-briefcase"></i>
                            Career Timeline
                        </h2>
                        <div class="professional-timeline">
                            ${careerTimeline.slice(0, 4).map((item, timelineIndex) => `
                                <div class="professional-timeline-item" style="animation-delay: ${timelineIndex * 0.1}s;">
                                    <div class="professional-timeline-dot"></div>
                                    <div class="professional-timeline-content">
                                        <div class="professional-timeline-header">
                                            <div class="professional-timeline-left">
                                                <div class="professional-timeline-role">${esc(item.role || 'Position')}</div>
                                                <div class="professional-timeline-company">${esc(item.company || 'Company')}</div>
                                            </div>
                                            <div class="professional-timeline-period">${esc(item.year_range || item.period || 'Period')}</div>
                                        </div>
                                        ${item.key_skills && item.key_skills.length > 0 ? `
                                        <div class="professional-timeline-skills">
                                            ${item.key_skills.slice(0, 6).map(skill =>
                    `<span class="professional-skill-tag">${esc(skill)}</span>`
                ).join('')}
                                        </div>
                                        ` : ''}
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    ` : ''}





                    ${tenurePrediction && Object.keys(tenurePrediction).length > 0 ? `
                    <!-- Tenure Prediction Section - All 6 Cards in One Grid -->
                    <div class="professional-section">
                        <h2 class="professional-section-title">
                            <i class="fas fa-clock"></i>
                            Tenure Prediction
                        </h2>
                        
                        <!-- Unified Grid with All 6 Cards -->
                        <div class="professional-score-grid" style="grid-template-columns: repeat(3, 1fr);">
                            <!-- Main Stats Cards (3) -->
                            <div class="professional-score-item technical">
                                <div class="professional-score-header">
                                    <div class="professional-score-name">
                                        <i class="fas fa-calendar-alt" style="margin-right: 8px; color: #10b981;"></i>
                                        Expected Tenure
                                    </div>
                                    <div class="professional-score-value" style="color: #10b981; font-size: 1.1rem;">
                                        ${esc(tenurePrediction.estimated_tenure || 'Not specified')}
                                    </div>
                                </div>
                            </div>
                            
                            <div class="professional-score-item leadership">
                                <div class="professional-score-header">
                                    <div class="professional-score-name">
                                        <i class="fas fa-chart-line" style="margin-right: 8px; color: #f59e0b;"></i>
                                        Retention Score
                                    </div>
                                    <div class="professional-score-value" style="color: #f59e0b; font-size: 1.1rem;">
                                        ${safeNum(tenurePrediction.tenure_score || 0, 0, 0, 100)}%
                                    </div>
                                </div>
                            </div>
                            
                            <div class="professional-score-item domain">
                                <div class="professional-score-header">
                                    <div class="professional-score-name">
                                        <i class="fas fa-thumbs-up" style="margin-right: 8px; color: #8b5cf6;"></i>
                                        Confidence Level
                                    </div>
                                    <div class="professional-score-value" style="color: #8b5cf6; font-size: 1.1rem;">
                                        ${esc(tenurePrediction.confidence_level || 'Medium')}
                                    </div>
                                </div>
                            </div>
                            
                            ${tenurePrediction.factors && Object.keys(tenurePrediction.factors).length > 0 ?
                            Object.entries(tenurePrediction.factors).filter(([factor, data]) => {
                                // Hide specific tenure prediction factors from frontend display
                                const hiddenFactors = [
                                    'experience_level_risk'
                                ];
                                return !hiddenFactors.includes(factor.toLowerCase());
                            }).map(([factor, data]) => {
                                const factorName = factor.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                                const factorScore = safeNum(data.score || 0, 0, 0, 100);
                                const scoreClass = factorScore >= 80 ? 'technical' : factorScore >= 60 ? 'leadership' : 'soft';
                                return `
                                    <!-- Factor Cards (3) -->
                                    <div class="professional-score-item ${scoreClass}">
                                        <div class="professional-score-header">
                                            <div class="professional-score-name">${esc(factorName)}</div>
                                            <div class="professional-score-value">${factorScore}%</div>
                                        </div>
                                        <div class="professional-score-bar">
                                            <div class="professional-score-fill" style="width: ${factorScore}%;"></div>
                                        </div>
                                        <div class="professional-score-comment">${esc(data.analysis || 'Good performance')}</div>
                                    </div>
                                    `;
                            }).join('') : ''
                        }
                        </div>
                    </div>
                    ` : ''}

                    <!-- Keywords Analysis - Always show if we have keyword data -->
                    <div class="professional-section">
                        <h2 class="professional-section-title">
                            <i class="fas fa-tags"></i>
                            Keywords Analysis
                        </h2>
                        <div class="professional-keywords-overview">
                            <div class="professional-keywords-chart">
                                <canvas id="keywordChart${index}" width="150" height="150"></canvas>
                            </div>
                            <div class="professional-keywords-details">
                                ${keywordCoverage.matched_keywords && keywordCoverage.matched_keywords.length > 0 ? `
                                <div class="professional-keyword-group matched">
                                    <h4><i class="fas fa-check-circle"></i> Matched Keywords (${keywordCoverage.matched_keywords.length})</h4>
                                    <div class="professional-keyword-tags">
                                        ${keywordCoverage.matched_keywords.map(keyword =>
                            `<span class="professional-keyword-tag matched">${esc(keyword)}</span>`
                        ).join('')}
                                    </div>
                                </div>
                                ` : `
                                <div class="professional-keyword-group matched">
                                    <h4><i class="fas fa-info-circle"></i> No Matched Keywords Found</h4>
                                    <p>No keywords were matched for this candidate.</p>
                                </div>
                                `}
                                ${keywordCoverage.missing_keywords && keywordCoverage.missing_keywords.length > 0 ? `
                                <div class="professional-keyword-group missing">
                                    <h4><i class="fas fa-exclamation-circle"></i> Missing Keywords (${keywordCoverage.missing_keywords.length})</h4>
                                    <div class="professional-keyword-tags">
                                        ${keywordCoverage.missing_keywords.map(keyword =>
                            `<span class="professional-keyword-tag missing">${esc(keyword)}</span>`
                        ).join('')}
                                    </div>
                                </div>
                                ` : `
                                <div class="professional-keyword-group missing">
                                    <h4><i class="fas fa-info-circle"></i> No Missing Keywords</h4>
                                    <p>All keywords were matched or none were analyzed.</p>
                                </div>
                                `}

                            </div>
                        </div>
                    </div>

                    <!-- Separator Line -->
                    <div class="hr-separator"></div>
                    
                    <!-- HR Actions Section -->
                    <div class="professional-section">
                        <h2 class="professional-section-title">
                            <i class="fas fa-tasks"></i>
                            HR Actions
                        </h2>
                        
                        <!-- Action Checkboxes -->
                        <div class="hr-action-checkboxes">
                            <label class="hr-checkbox-item selected">
                                <input type="checkbox" 
                                       class="hr-checkbox" 
                                       data-status="selected">
                                <span class="hr-checkbox-label">
                                    <i class="fas fa-check-circle"></i>
                                    Selected
                                </span>
                            </label>
                            <label class="hr-checkbox-item shortlisted">
                                <input type="checkbox" 
                                       class="hr-checkbox" 
                                       data-status="shortlisted">
                                <span class="hr-checkbox-label">
                                    <i class="fas fa-star"></i>
                                    Shortlisted
                                </span>
                            </label>
                            <label class="hr-checkbox-item interviewed">
                                <input type="checkbox" 
                                       class="hr-checkbox" 
                                       data-status="interviewed">
                                <span class="hr-checkbox-label">
                                    <i class="fas fa-video"></i>
                                    Interviewed
                                </span>
                            </label>
                            <label class="hr-checkbox-item rejected">
                                <input type="checkbox" 
                                       class="hr-checkbox" 
                                       data-status="rejected">
                                <span class="hr-checkbox-label">
                                    <i class="fas fa-times-circle"></i>
                                    Rejected
                                </span>
                            </label>
                        </div>
                        
                        <!-- Comments Section -->
                        <div class="hr-comments-section">
                            <label for="comments-${index}" class="hr-comments-label">
                                <i class="fas fa-comment-alt"></i>
                                HR Comments & Notes
                            </label>
                            <textarea 
                                id="comments-${index}" 
                                class="hr-comments-textarea"
                                placeholder="Add your comments, interview notes, or feedback about this candidate..."
                                rows="3"></textarea>
                        </div>
                        
                        <!-- Contact & Download Buttons -->
                        <div class="professional-action-buttons">
                            <button type="button"
                                    class="professional-action-btn primary js-contact-candidate">
                                <i class="fas fa-envelope"></i> 
                                Contact Candidate
                            </button>
                            <button type="button"
                                    class="professional-action-btn secondary js-schedule-interview">
                                <i class="fas fa-calendar-plus"></i> 
                                Schedule Interview
                            </button>
                            <button type="button"
                                    class="professional-action-btn tertiary js-download-resume">
                                <i class="fas fa-download"></i> 
                                Download Resume
                            </button>
                            <button type="button"
                                    class="professional-action-btn quaternary js-export-candidate-report">
                                <i class="fas fa-file-export"></i> 
                                Export Report
                            </button>
                        </div>
                    </div>
                </div>
            `;

                card.querySelectorAll('.hr-checkbox').forEach((checkbox) => {
                    checkbox.addEventListener('change', () => {
                        setCandidateStatus(finalCandidateName, checkbox.dataset.status, checkbox);
                    });
                });

                const commentsTextarea = card.querySelector('.hr-comments-textarea');
                if (commentsTextarea) {
                    commentsTextarea.addEventListener('change', () => {
                        saveCandidateComment(finalCandidateName, commentsTextarea.value);
                    });
                }

                card.querySelector('.js-contact-candidate')?.addEventListener('click', () => {
                    if (canEmailCandidate) {
                        window.location.href = `mailto:${safeEmailValue}`;
                    } else {
                        showNotification('No valid email address is available for this candidate.', 'error');
                    }
                });

                card.querySelector('.js-schedule-interview')?.addEventListener('click', () => {
                    scheduleInterview(finalCandidateName, canEmailCandidate ? safeEmailValue : '');
                });

                card.querySelector('.js-download-resume')?.addEventListener('click', () => {
                    downloadResume(candidateFilePath);
                });

                card.querySelector('.js-export-candidate-report')?.addEventListener('click', () => {
                    exportCandidateReport(finalCandidateName, index, candidateFilePath);
                });

                resultsContainer.appendChild(card);

                console.log('Card HTML successfully created and appended');

                // Initialize keyword chart if we have keyword data
                if (keywordCoverage.matched_keywords || keywordCoverage.missing_keywords) {
                    setTimeout(() => {
                        const canvas = document.getElementById(`keywordChart${index}`);
                        if (canvas && typeof Chart !== 'undefined') {
                            const ctx = canvas.getContext('2d');
                            const matched = keywordCoverage.matched_keywords ? keywordCoverage.matched_keywords.length : 0;
                            const missing = keywordCoverage.missing_keywords ? keywordCoverage.missing_keywords.length : 0;

                            new Chart(ctx, {
                                type: 'doughnut',
                                data: {
                                    labels: ['Matched', 'Missing'],
                                    datasets: [{
                                        data: [matched, missing],
                                        backgroundColor: ['#10b981', '#ef4444'],
                                        borderWidth: 0
                                    }]
                                },
                                options: {
                                    responsive: false,
                                    plugins: {
                                        legend: {
                                            position: 'bottom',
                                            labels: {
                                                boxWidth: 12,
                                                padding: 10,
                                                font: {
                                                    size: 12
                                                }
                                            }
                                        }
                                    }
                                }
                            });
                        }
                    }, 100);
                }

                // Load saved candidate data
                loadCandidateData();

            } catch (htmlError) {
                console.error('Error creating HTML template:', htmlError);
                throw htmlError; // Re-throw to be caught by outer catch block
            }

        } catch (error) {
            console.error('Error in generateDetailedCandidateCard:', error);

            // Show error message in the results container
            resultsContainer.innerHTML = `
                <div class="flex items-center justify-center h-full min-h-[400px]">
                    <div class="text-center max-w-md mx-auto p-8">
                        <div class="w-20 h-20 bg-orange-100 rounded-full flex items-center justify-center mx-auto mb-6">
                            <i class="fas fa-exclamation-triangle text-orange-500 text-2xl"></i>
                        </div>
                        <h3 class="text-xl font-semibold text-gray-800 mb-4">Unable to Display Candidate Details</h3>
                        <p class="text-gray-600 mb-6 leading-relaxed">
                            We encountered an issue while processing this candidate's information. Please try selecting a different candidate or refresh the page.
                        </p>
                        <div class="space-y-3">
                            <button onclick="location.reload()" class="w-full bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition-colors">
                                <i class="fas fa-refresh mr-2"></i>
                                Refresh Page
                            </button>
                            <p class="text-sm text-gray-500">
                                <i class="fas fa-info-circle mr-1"></i>
                                Our support team has been notified about this issue.
                            </p>
                        </div>
                    </div>
                </div>
            `;
        }
    }


    function initializeVectorSearchPage() {
        const vectorQuery = document.getElementById('vectorQuery');
        const vectorSearchBtn = document.getElementById('vectorSearchBtn');
        const sampleQueriesBtn = document.getElementById('sampleQueriesBtn');
        const clearResultsBtn = document.getElementById('clearResultsBtn');
        const sampleQueriesSection = document.getElementById('sampleQueriesSection');
        const vectorSearchLoading = document.getElementById('vectorSearchLoading');
        const vectorSearchResults = document.getElementById('vectorSearchResults');
        const noResults = document.getElementById('noResults');

        // Vector search page DOM not present (e.g. on /dashboard) - bail out cleanly.
        if (!vectorSearchBtn || !vectorQuery) return;

        // Handle search button click
        vectorSearchBtn.addEventListener('click', () => {
            const query = vectorQuery.value.trim();
            if (query) {
                performVectorSearch(query);
            }
        });

        // Handle enter key press
        vectorQuery.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                vectorSearchBtn.click();
            }
        });

        // Handle sample queries toggle
        sampleQueriesBtn.addEventListener('click', () => {
            sampleQueriesSection.classList.toggle('hidden');
        });

        // "Try Sample Queries" button on the No Results state opens the same panel.
        const noResultsSamplesBtn = document.getElementById('noResultsSamplesBtn');
        if (noResultsSamplesBtn) {
            noResultsSamplesBtn.addEventListener('click', () => {
                sampleQueriesSection.classList.remove('hidden');
                sampleQueriesSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            });
        }

        // Handle sample query buttons
        const sampleQueryButtons = document.querySelectorAll('.sample-query-btn');
        console.log('Found sample query buttons:', sampleQueryButtons.length); // Debug log

        sampleQueryButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                let queryText = '';

                // Check if this is a complex query with nested div
                const nestedDiv = btn.querySelector('div.text-sm');
                if (nestedDiv) {
                    // For complex queries, extract the full text content
                    queryText = nestedDiv.textContent.trim();
                } else {
                    // For simple queries, get text content excluding icon elements
                    const iconElement = btn.querySelector('i');
                    if (iconElement) {
                        // Clone the button and remove the icon to get clean text
                        const tempBtn = btn.cloneNode(true);
                        const tempIcon = tempBtn.querySelector('i');
                        if (tempIcon) {
                            tempIcon.remove();
                        }
                        queryText = tempBtn.textContent.trim();
                    } else {
                        // Fallback: just use all text content
                        queryText = btn.textContent.trim();
                    }
                }

                console.log('Sample query clicked:', queryText); // Debug log

                if (queryText) {
                    vectorQuery.value = queryText;
                    sampleQueriesSection.classList.add('hidden');
                    performVectorSearch(queryText);
                } else {
                    console.error('No query text extracted from button');
                }
            });
        });

        // Handle clear results
        clearResultsBtn.addEventListener('click', () => {
            vectorSearchResults.classList.add('hidden');
            noResults.classList.add('hidden');
            vectorQuery.value = '';
        });

        // Show/hide job title field based on search method
        document.querySelectorAll('input[name="searchMethod"]').forEach(radio => {
            radio.addEventListener('change', function () {
                const jobTitleSection = document.getElementById('jobTitleSection');
                if (this.value === 'hr-scorecard') {
                    jobTitleSection.classList.remove('hidden');
                } else {
                    jobTitleSection.classList.add('hidden');
                }
            });
        });

        function performVectorSearch(query) {
            // Hide previous results
            vectorSearchResults.classList.add('hidden');
            noResults.classList.add('hidden');

            // Get selected search method and result count
            const searchMethod = document.querySelector('input[name="searchMethod"]:checked').value;
            const resultCount = document.getElementById('resultCount').value;

            // Show loading with appropriate message
            const loadingDiv = document.getElementById('vectorSearchLoading');
            const loadingText = loadingDiv.querySelector('span');

            switch (searchMethod) {
                case 'single':
                    loadingText.textContent = 'Searching vector store...';
                    break;
                case 'multi':
                    loadingText.textContent = 'Executing 4-query search (experience + skills + role + domain)...';
                    break;
                case 'enhanced':
                    loadingText.textContent = 'Running enhanced LLM pipeline (keyword extraction → search → ranking)...';
                    break;
                case 'hr-scorecard':
                    loadingText.textContent = 'Generating comprehensive HR scorecards for candidates...';
                    break;
            }

            loadingDiv.classList.remove('hidden');

            // Determine API endpoint based on search method
            let apiEndpoint;
            switch (searchMethod) {
                case 'single':
                    apiEndpoint = '/api/search-vector';
                    break;
                case 'multi':
                    apiEndpoint = '/api/multi-query-search';
                    break;
                case 'enhanced':
                    apiEndpoint = '/api/enhanced-search';
                    break;
                case 'hr-scorecard':
                    apiEndpoint = '/api/hr-scorecard-search';
                    break;
                default:
                    apiEndpoint = '/api/search-vector';
            }

            const startTime = Date.now();
            const formData = new FormData();
            formData.append('query', query);
            formData.append('result_count', resultCount);
            window.__lastSearchQuery = query;

            if (searchMethod === 'enhanced') {
                formData.append('use_llm_pipeline', 'true');
            }

            if (searchMethod === 'hr-scorecard') {
                const jobTitle = document.getElementById('jobTitle').value.trim() || 'Position';
                formData.append('job_title', jobTitle);
            }

            fetch(apiEndpoint, {
                method: 'POST',
                body: formData
            })
                .then(response => response.json())
                .then(data => {
                    const endTime = Date.now();
                    const searchTime = ((endTime - startTime) / 1000).toFixed(2);

                    // Hide loading
                    vectorSearchLoading.classList.add('hidden');

                    if (data.results && data.results.length > 0) {
                        // Use enhanced display for multi-query, enhanced, and HR scorecard searches
                        if (searchMethod === 'multi' || searchMethod === 'enhanced' || searchMethod === 'hr-scorecard') {
                            displayEnhancedVectorResults(data, searchTime);
                        } else {
                            displayVectorResults(data, searchTime);
                        }
                    } else {
                        noResults.classList.remove('hidden');
                    }
                })
                .catch(error => {
                    console.error('Vector search error:', error);
                    vectorSearchLoading.classList.add('hidden');

                    // Show error message
                    const errorDiv = document.createElement('div');
                    errorDiv.className = 'bg-red-50 border border-red-200 rounded-xl p-6 text-center';
                    errorDiv.innerHTML = `
                    <div class="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                        <i class="fas fa-exclamation-triangle text-red-500 text-xl"></i>
                    </div>
                    <h3 class="text-lg font-medium text-red-900 mb-2">Search Failed</h3>
                    <p class="text-red-700 mb-4">An error occurred while searching the vector store.</p>
                    <p class="text-sm text-red-600">${error.message || 'Unknown error'}</p>
                `;

                    // Replace loading with error
                    vectorSearchLoading.parentNode.insertBefore(errorDiv, vectorSearchLoading);
                });
        }

        function displayVectorResults(data, searchTime) {
            const resultsSubtitle = document.getElementById('resultsSubtitle');
            const searchTimeEl = document.getElementById('searchTime');
            const resultsContainer = document.getElementById('resultsContainer');

            resultsSubtitle.textContent = `${data.total_results} results found for "${data.query}"`;
            searchTimeEl.textContent = `${searchTime}s`;

            resultsContainer.innerHTML = data.results.map((result, index) => {
                let contentPreview = '';
                let snippets = '';

                // Extract content preview
                if (result.content) {
                    const contentKeys = Object.keys(result.content);
                    if (contentKeys.length > 0) {
                        const firstKey = contentKeys[0];
                        const content = result.content[firstKey];
                        if (typeof content === 'string') {
                            contentPreview = content.length > 200 ? content.substring(0, 200) + '...' : content;
                        }
                    }
                }

                // Extract snippets
                if (result.snippets && result.snippets.length > 0) {
                    snippets = result.snippets.slice(0, 3).map(snippet => {
                        const text = snippet.snippet || '';
                        return text.length > 150 ? text.substring(0, 150) + '...' : text;
                    }).join('</p><p class="text-sm text-gray-600 mt-2">');
                }

                return `
                    <div class="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
                        <div class="flex items-start justify-between mb-3">
                            <div class="flex items-center space-x-2">
                                <span class="w-6 h-6 bg-blue-100 text-blue-600 rounded-full text-xs font-bold flex items-center justify-center">${index + 1}</span>
                                <h4 class="font-medium text-gray-900">Document ${result.id || 'Unknown'}</h4>
                            </div>
                            ${result.relevance_score ? `<span class="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full">Score: ${result.relevance_score.toFixed(2)}</span>` : ''}
                        </div>
                        
                        ${result.document_name && result.document_name !== 'Unknown' ? `
                            <p class="text-sm text-gray-600 mb-2">
                                <i class="fas fa-file-alt mr-1"></i>
                                ${result.document_name}
                            </p>
                        ` : ''}
                        
                        ${contentPreview ? `
                            <div class="mb-3">
                                <h5 class="text-xs font-medium text-gray-700 mb-1">Content Preview:</h5>
                                <p class="text-sm text-gray-600 bg-gray-50 p-2 rounded border-l-2 border-blue-300">${contentPreview}</p>
                            </div>
                        ` : ''}
                        
                        ${snippets ? `
                            <div class="mb-3">
                                <h5 class="text-xs font-medium text-gray-700 mb-1">Relevant Snippets:</h5>
                                <div class="space-y-2">
                                    <p class="text-sm text-gray-600">${snippets}</p>
                                </div>
                            </div>
                        ` : ''}

                        <div class="flex items-center justify-between text-xs text-gray-500 mt-3 pt-3 border-t border-gray-100">
                            <span>Document ID: ${result.id || 'N/A'}</span>
                            <span>Datastore: ${data.datastore_id}</span>
                        </div>
                    </div>
                `;
            }).join('');

            vectorSearchResults.classList.remove('hidden');
        }

        function displayEnhancedVectorResults(data, searchTime) {
            const resultsSubtitle = document.getElementById('resultsSubtitle');
            const searchTimeEl = document.getElementById('searchTime');
            const resultsContainer = document.getElementById('resultsContainer');

            resultsSubtitle.textContent = `${data.total_results} results found for "${data.query}" with AI analysis`;
            searchTimeEl.textContent = `${searchTime}s`;

            let resultsHtml = '';

            // Show Gemini Analysis for top result if available
            if (data.top_result_analysis && data.results.length > 0) {
                const analysis = data.top_result_analysis;
                const topResult = data.results[0];

                resultsHtml += `
                    <div class="bg-gradient-to-r from-purple-50 to-blue-50 border-2 border-purple-200 rounded-xl p-6 mb-6">
                        <div class="flex items-center justify-between mb-4">
                            <div class="flex items-center space-x-3">
                                <div class="w-10 h-10 bg-purple-100 rounded-full flex items-center justify-center">
                                    <i class="fas fa-brain text-purple-600 text-lg"></i>
                                </div>
                                <div>
                                    <h3 class="text-xl font-bold text-purple-900">AI Analysis - Top Match</h3>
                                    <p class="text-sm text-purple-700">Analyzed by ${analysis.analyzed_by || 'Gemini AI'}</p>
                                </div>
                            </div>
                            ${analysis.match_score ? `
                                <div class="text-center">
                                    <div class="text-3xl font-bold text-purple-600">${analysis.match_score}</div>
                                    <div class="text-xs text-purple-500 font-medium">MATCH SCORE</div>
                                </div>
                            ` : ''}
                        </div>
                        
                        ${analysis.success ? `
                            <div class="bg-white rounded-lg p-4 mb-4">
                                <div class="prose prose-sm max-w-none">
                                    <div class="whitespace-pre-line text-gray-800">${analysis.analysis}</div>
                                </div>
                            </div>
                        ` : `
                            <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-4">
                                <div class="flex items-center">
                                    <i class="fas fa-exclamation-triangle text-yellow-500 mr-2"></i>
                                    <span class="text-yellow-800">Analysis unavailable: ${analysis.error || 'Unknown error'}</span>
                                </div>
                            </div>
                        `}
                        
                        <div class="text-xs text-purple-600 bg-purple-100 rounded px-2 py-1 inline-block">
                            <i class="fas fa-document mr-1"></i>
                            Document: ${topResult.document_name || topResult.id || 'Unknown'}
                        </div>
                    </div>
                `;
            }

            // Show all search results
            resultsHtml += data.results.map((result, index) => {
                let contentPreview = '';
                let snippets = '';

                // Extract content preview
                if (result.content) {
                    const contentKeys = Object.keys(result.content);
                    if (contentKeys.length > 0) {
                        const firstKey = contentKeys[0];
                        const content = result.content[firstKey];
                        if (typeof content === 'string') {
                            contentPreview = content.length > 200 ? content.substring(0, 200) + '...' : content;
                        }
                    }
                }

                // Extract snippets
                if (result.snippets && result.snippets.length > 0) {
                    snippets = result.snippets.slice(0, 3).map(snippet => {
                        const text = snippet.snippet || '';
                        return text.length > 150 ? text.substring(0, 150) + '...' : text;
                    }).join('</p><p class="text-sm text-gray-600 mt-2">');
                }

                const hasAnalysis = index === 0 && result.gemini_analysis;
                const borderClass = hasAnalysis ? 'border-purple-300 bg-purple-50' : 'border-gray-200';

                return `
                    <div class="border ${borderClass} rounded-lg p-4 hover:shadow-md transition-shadow">
                        <div class="flex items-start justify-between mb-3">
                            <div class="flex items-center space-x-2">
                                <span class="w-6 h-6 ${hasAnalysis ? 'bg-purple-100 text-purple-600' : 'bg-blue-100 text-blue-600'} rounded-full text-xs font-bold flex items-center justify-center">${index + 1}</span>
                                <h4 class="font-medium text-gray-900">Document ${result.id || 'Unknown'}</h4>
                                ${hasAnalysis ? '<span class="text-xs bg-purple-200 text-purple-800 px-2 py-1 rounded-full font-medium">AI Analyzed</span>' : ''}
                            </div>
                            ${result.relevance_score ? `<span class="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full">Score: ${result.relevance_score.toFixed(2)}</span>` : ''}
                        </div>
                        
                        ${result.document_name && result.document_name !== 'Unknown' ? `
                            <p class="text-sm text-gray-600 mb-2">
                                <i class="fas fa-file-alt mr-1"></i>
                                ${result.document_name}
                            </p>
                        ` : ''}
                        
                        ${contentPreview ? `
                            <div class="mb-3">
                                <h5 class="text-xs font-medium text-gray-700 mb-1">Content Preview:</h5>
                                <p class="text-sm text-gray-600 bg-gray-50 p-2 rounded border-l-2 border-blue-300">${contentPreview}</p>
                            </div>
                        ` : ''}
                        
                        ${snippets ? `
                            <div class="mb-3">
                                <h5 class="text-xs font-medium text-gray-700 mb-1">Relevant Snippets:</h5>
                                <div class="space-y-2">
                                    <p class="text-sm text-gray-600">${snippets}</p>
                                </div>
                            </div>
                        ` : ''}

                        <div class="flex items-center justify-between text-xs text-gray-500 mt-3 pt-3 border-t border-gray-100">
                            <span>Document ID: ${result.id || 'N/A'}</span>
                            <span>Datastore: ${data.datastore_id}</span>
                        </div>
                    </div>
                `;
            }).join('');

            resultsContainer.innerHTML = resultsHtml;
            vectorSearchResults.classList.remove('hidden');
        }
    }

    function initializeHistoryPage() {
        // Reset paging state when entering the page so we always start on page 1.
        window.__historyPageState = { page: 1, pageSize: 25, total: 0 };
        // Load search history from database
        loadSearchHistoryFromDB(1, 25);

        // Handle start searching button
        const startSearchingBtn = document.getElementById('start-searching');
        if (startSearchingBtn) {
            startSearchingBtn.addEventListener('click', () => {
                setActiveLink(searchResumesLink);
                loadPage('searchResumes');
            });
        }
    }

    async function loadSearchHistoryFromDB(page, pageSize) {
        const state = window.__historyPageState = window.__historyPageState || { page: 1, pageSize: 25, total: 0 };
        if (typeof page === 'number' && page >= 1) state.page = page;
        if (typeof pageSize === 'number' && pageSize >= 1) state.pageSize = pageSize;
        try {
            const qs = `?page=${encodeURIComponent(state.page)}&page_size=${encodeURIComponent(state.pageSize)}`;
            const response = await fetch(`/api/search-history${qs}`, {
                method: 'GET',
                credentials: 'same-origin', // Ensure cookies are sent
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                console.error('Search history response not ok:', response.status);
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            if (data.success && Array.isArray(data.history)) {
                state.total = Number.isFinite(data.total) ? data.total : data.history.length;
                state.page = data.page || state.page;
                state.pageSize = data.page_size || state.pageSize;
                displaySearchHistory(data.history);
                renderHistoryPagination();
            } else {
                console.error('Search history response indicates failure:', data);
                // Show empty state
                state.total = 0;
                displaySearchHistory([]);
                renderHistoryPagination();
            }
        } catch (error) {
            console.error('Error loading search history:', error);
            // Show empty state with error message
            const historyTableBody = document.getElementById('history-table-body');
            if (historyTableBody) {
                historyTableBody.innerHTML = `
                    <div class="col-span-12 text-center py-12">
                        <div class="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                            <i class="fas fa-exclamation-triangle text-red-500 text-lg"></i>
                        </div>
                        <h3 class="text-lg font-medium text-gray-900 mb-2">Failed to load search history</h3>
                        <p class="text-gray-600 text-sm mb-4">There was an error loading your search history. Please try refreshing the page.</p>
                        <button onclick="location.reload()" class="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium">
                            <i class="fas fa-redo mr-2"></i>
                            Refresh Page
                        </button>
                    </div>
                `;
            }
        }
    }

    function displaySearchHistory(historyData) {
        const historyTableBody = document.getElementById('history-table-body');
        if (!historyTableBody) return;

        // Store original data for filtering
        window.originalHistoryData = historyData;

        // Render the table rows
        renderHistoryTableRows(historyData);

        // Initialize search functionality (only once)
        initializeHistorySearch();
    }

    function renderHistoryTableRows(historyData) {
        const historyTableBody = document.getElementById('history-table-body');
        if (!historyTableBody) return;

        if (historyData.length === 0) {
            historyTableBody.innerHTML = `
                <div class="col-span-12 text-center py-12">
                    <div class="w-16 h-16 bg-gray-200 rounded-full flex items-center justify-center mx-auto mb-4">
                        <i class="fas fa-history text-gray-400 text-lg"></i>
                    </div>
                    <h3 class="text-lg font-medium text-gray-900 mb-2">No search history yet</h3>
                    <p class="text-gray-600 text-sm mb-4">Start searching for candidates to build your search history</p>
                    <button id="start-searching" class="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium">
                        <i class="fas fa-search mr-2"></i>
                        Start Searching
                    </button>
                </div>
            `;

            // Re-add event listener for start searching button
            const startSearchingBtn = document.getElementById('start-searching');
            if (startSearchingBtn) {
                startSearchingBtn.addEventListener('click', () => {
                    setActiveLink(searchResumesLink);
                    loadPage('searchResumes');
                });
            }
        } else {
            historyTableBody.innerHTML = historyData.map((search, index) => {
                const searchDate = new Date(search.search_timestamp || search.timestamp);
                const truncatedQuery = truncateText(search.search_query || search.query, 60);
                const candidatesCount = search.actual_results || search.result_count || 0;

                return `
                    <div class="px-6 py-4 hover:bg-gray-50 transition-colors cursor-pointer history-row" data-search-id="${search.id}" data-query="${search.search_query || search.query}">
                        <div class="grid grid-cols-12 gap-4 items-center">
                            <!-- Job Description -->
                            <div class="col-span-4">
                                <div class="text-sm font-medium text-gray-900" title="${search.search_query || search.query}">
                                    ${truncatedQuery}
                                </div>
                                ${search.job_title ? `<div class="text-xs text-gray-500 mt-1">${search.job_title}</div>` : ''}
                            </div>
                            
                            <!-- Date & Time -->
                            <div class="col-span-2">
                                <div class="text-sm text-gray-900">${formatDate(searchDate)}</div>
                                <div class="text-xs text-gray-500">${formatTime(searchDate)}</div>
                            </div>
                            
                            <!-- Candidates Count -->
                            <div class="col-span-2">
                                <div class="flex items-center">
                                    <span class="text-sm font-medium text-gray-900">${candidatesCount}</span>
                                    <span class="text-xs text-gray-500 ml-1">candidates found</span>
                                </div>
                            </div>
                            
                            <!-- Top Results Preview -->
                            <div class="col-span-3">
                                <div class="space-y-1">
                                    ${search.top_results && search.top_results.length > 0 ?
                        search.top_results.slice(0, 3).map(result => `
                                            <div class="flex items-center justify-between bg-gray-50 rounded px-2 py-1">
                                                <div class="flex items-center space-x-2">
                                                    <div class="w-4 h-4 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center">
                                                        <span class="text-white font-bold text-xs">${result.name ? result.name.charAt(0).toUpperCase() : '?'}</span>
                                                    </div>
                                                    <span class="text-xs font-medium text-gray-700 truncate max-w-[80px]" title="${result.name || 'Unknown'}">
                                                        ${truncateText(result.name || 'Unknown', 12)}
                                                    </span>
                                                </div>
                                                <span class="text-xs font-bold text-green-600">${result.score || 0}%</span>
                                            </div>
                                        `).join('') :
                        '<span class="text-xs text-gray-400">No preview available</span>'
                    }
                                    ${search.top_results && search.top_results.length > 3 ?
                        `<div class="text-xs text-gray-500 text-center">+${search.top_results.length - 3} more candidates</div>` : ''
                    }
                                </div>
                            </div>
                            
                            <!-- Actions -->
                            <div class="col-span-1 text-center">
                                <div class="flex items-center justify-center space-x-1">
                                    <button class="view-search p-1.5 text-blue-600 hover:bg-blue-50 rounded transition-colors" 
                                            data-search-id="${search.id}" data-query="${search.search_query || search.query}"
                                            title="View Results">
                                        <i class="fas fa-eye text-xs"></i>
                                    </button>
                                    <button class="delete-search p-1.5 text-red-600 hover:bg-red-50 rounded transition-colors" 
                                            data-search-id="${search.id}"
                                            title="Delete Search">
                                        <i class="fas fa-trash text-xs"></i>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');

            // Re-attach event listeners after rendering
            attachHistoryEventListeners();
        }
    }

    function renderHistoryPagination() {
        const container = document.getElementById('history-pagination');
        if (!container) return;
        const state = window.__historyPageState || { page: 1, pageSize: 25, total: 0 };
        const total = Math.max(0, Number(state.total) || 0);
        const pageSize = Math.max(1, Number(state.pageSize) || 25);
        const totalPages = Math.max(1, Math.ceil(total / pageSize));
        const page = Math.min(Math.max(1, Number(state.page) || 1), totalPages);

        if (total === 0) {
            container.classList.add('hidden');
            container.innerHTML = '';
            return;
        }

        const from = (page - 1) * pageSize + 1;
        const to = Math.min(total, page * pageSize);
        const prevDisabled = page <= 1;
        const nextDisabled = page >= totalPages;
        const btnBase = 'inline-flex items-center px-3 py-1.5 rounded-md border text-xs font-medium transition-colors';
        const btnEnabled = 'bg-white border-gray-300 text-gray-700 hover:bg-gray-100';
        const btnDisabled = 'bg-gray-100 border-gray-200 text-gray-400 cursor-not-allowed';

        container.classList.remove('hidden');
        container.innerHTML = `
            <div>
                Showing <span class="font-semibold text-gray-900">${from}</span>-<span class="font-semibold text-gray-900">${to}</span>
                of <span class="font-semibold text-gray-900">${total}</span>
            </div>
            <div class="flex items-center space-x-2">
                <label class="text-xs text-gray-500 mr-2">
                    Page size:
                    <select id="history-page-size" class="ml-1 border border-gray-300 rounded px-1 py-0.5 text-xs">
                        ${[10, 25, 50, 100].map(s => `<option value="${s}" ${s === pageSize ? 'selected' : ''}>${s}</option>`).join('')}
                    </select>
                </label>
                <button id="history-prev-page" class="${btnBase} ${prevDisabled ? btnDisabled : btnEnabled}" ${prevDisabled ? 'disabled' : ''}>
                    <i class="fas fa-chevron-left mr-1 text-[10px]"></i> Prev
                </button>
                <span class="text-xs text-gray-600">Page <span class="font-semibold text-gray-900">${page}</span> / ${totalPages}</span>
                <button id="history-next-page" class="${btnBase} ${nextDisabled ? btnDisabled : btnEnabled}" ${nextDisabled ? 'disabled' : ''}>
                    Next <i class="fas fa-chevron-right ml-1 text-[10px]"></i>
                </button>
            </div>
        `;

        const prevBtn = document.getElementById('history-prev-page');
        const nextBtn = document.getElementById('history-next-page');
        const sizeSel = document.getElementById('history-page-size');
        if (prevBtn && !prevDisabled) {
            prevBtn.addEventListener('click', () => loadSearchHistoryFromDB(page - 1, pageSize));
        }
        if (nextBtn && !nextDisabled) {
            nextBtn.addEventListener('click', () => loadSearchHistoryFromDB(page + 1, pageSize));
        }
        if (sizeSel) {
            sizeSel.addEventListener('change', (e) => {
                const newSize = parseInt(e.target.value, 10) || 25;
                loadSearchHistoryFromDB(1, newSize);
            });
        }
    }

    function attachHistoryEventListeners() {        // Attach click listeners to view buttons
        document.querySelectorAll('.view-search').forEach(button => {
            button.addEventListener('click', (e) => {
                e.stopPropagation();
                const searchId = button.getAttribute('data-search-id');
                const query = button.getAttribute('data-query');
                window.loadSavedSearch(searchId, query);
            });
        });

        // Attach click listeners to delete buttons
        document.querySelectorAll('.delete-search').forEach(button => {
            button.addEventListener('click', async (e) => {
                e.stopPropagation();
                const searchId = button.getAttribute('data-search-id');

                if (confirm('Are you sure you want to delete this search from history?')) {
                    try {
                        const response = await fetch(`/api/search-history/${searchId}`, {
                            method: 'DELETE',
                            credentials: 'same-origin',
                            headers: {
                                'Content-Type': 'application/json'
                            }
                        });

                        if (response.ok) {
                            // Reload current page (clamp later if it becomes empty).
                            const st = window.__historyPageState || { page: 1, pageSize: 25 };
                            loadSearchHistoryFromDB(st.page, st.pageSize);
                            showNotification('Search deleted successfully', 'success');
                        } else {
                            showNotification('Failed to delete search', 'error');
                        }
                    } catch (error) {
                        console.error('Error deleting search:', error);
                        showNotification('Error deleting search', 'error');
                    }
                }
            });
        });

        // Attach click listeners to history rows
        document.querySelectorAll('.history-row').forEach(row => {
            row.addEventListener('click', (e) => {
                // Only trigger if not clicking on a button
                if (!e.target.closest('button')) {
                    const searchId = row.getAttribute('data-search-id');
                    const query = row.getAttribute('data-query');
                    window.loadSavedSearch(searchId, query);
                }
            });
        });
    }

    // Helper functions for formatting
    function truncateText(text, maxLength) {
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }

    function formatDate(date) {
        return date.toLocaleDateString('en-US', {
            month: 'numeric',
            day: 'numeric',
            year: 'numeric'
        });
    }

    function formatTime(date) {
        return date.toLocaleTimeString('en-US', {
            hour: 'numeric',
            minute: '2-digit',
            second: '2-digit',
            hour12: true
        });
    }

    function initializeHistorySearch() {
        const searchInput = document.getElementById('history-search');
        const clearButton = document.getElementById('clear-history');

        // Prevent multiple event listeners
        if (searchInput && !searchInput.hasAttribute('data-initialized')) {
            searchInput.setAttribute('data-initialized', 'true');

            // Add debouncing to prevent too many filter calls
            let searchTimeout;
            searchInput.addEventListener('input', (e) => {
                const searchTerm = e.target.value.toLowerCase();

                // Clear previous timeout
                clearTimeout(searchTimeout);

                // Set new timeout for debounced search
                searchTimeout = setTimeout(() => {
                    filterHistoryData(searchTerm);
                }, 150); // 150ms delay
            });
        }

        if (clearButton && !clearButton.hasAttribute('data-initialized')) {
            clearButton.setAttribute('data-initialized', 'true');
            clearButton.addEventListener('click', async () => {
                if (!confirm('Are you sure you want to clear all search history? This action cannot be undone.')) return;
                clearButton.disabled = true;
                const originalLabel = clearButton.innerHTML;
                clearButton.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Clearing...';
                try {
                    const resp = await fetch('/api/search-history', { method: 'DELETE', credentials: 'same-origin' });
                    if (!resp.ok) throw new Error('HTTP ' + resp.status);
                    const data = await resp.json();
                    window.originalHistoryData = [];
                    const tableBody = document.getElementById('history-table-body');
                    if (tableBody) {
                        tableBody.innerHTML = `
                            <div class="col-span-12 text-center py-12">
                                <i class="fas fa-inbox text-gray-300 text-3xl mb-3"></i>
                                <p class="text-gray-500">No search history yet</p>
                            </div>`;
                    }
                    if (typeof showNotification === 'function') {
                        showNotification(`Cleared ${data.deleted || 0} search${(data.deleted||0)===1?'':'es'}`, 'success');
                    }
                } catch (err) {
                    console.error('Failed to clear history:', err);
                    if (typeof showNotification === 'function') {
                        showNotification('Failed to clear history: ' + err.message, 'error');
                    } else {
                        alert('Failed to clear history: ' + err.message);
                    }
                } finally {
                    clearButton.disabled = false;
                    clearButton.innerHTML = originalLabel;
                }
            });
        }
    }

    function filterHistoryData(searchTerm) {
        if (!window.originalHistoryData) return;

        const filteredData = window.originalHistoryData.filter(search => {
            const query = (search.search_query || search.query || '').toLowerCase();
            const jobTitle = (search.job_title || '').toLowerCase();
            return query.includes(searchTerm) || jobTitle.includes(searchTerm);
        });

        const historyTableBody = document.getElementById('history-table-body');
        if (filteredData.length === 0 && searchTerm) {
            historyTableBody.innerHTML = `
                <div class="col-span-12 text-center py-8">
                    <i class="fas fa-search text-gray-300 text-2xl mb-2"></i>
                    <p class="text-gray-500 text-sm">No search history found matching "${searchTerm}"</p>
                </div>
            `;
        } else {
            // Only update the table body content, don't reinitialize search
            renderHistoryTableRows(filteredData);
        }
    }

    function renderHistoryTableRows(historyData) {
        const historyTableBody = document.getElementById('history-table-body');
        if (!historyTableBody) return;

        if (historyData.length === 0) {
            historyTableBody.innerHTML = `
                <div class="col-span-12 text-center py-12">
                    <div class="w-16 h-16 bg-gray-200 rounded-full flex items-center justify-center mx-auto mb-4">
                        <i class="fas fa-history text-gray-400 text-lg"></i>
                    </div>
                    <h3 class="text-lg font-medium text-gray-900 mb-2">No search history yet</h3>
                    <p class="text-gray-600 text-sm mb-4">Start searching for candidates to build your search history</p>
                    <button id="start-searching" class="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium">
                        <i class="fas fa-search mr-2"></i>
                        Start Searching
                    </button>
                </div>
            `;

            // Re-add event listener for start searching button
            const startSearchingBtn = document.getElementById('start-searching');
            if (startSearchingBtn) {
                startSearchingBtn.addEventListener('click', () => {
                    setActiveLink(searchResumesLink);
                    loadPage('searchResumes');
                });
            }
        } else {
            historyTableBody.innerHTML = historyData.map((search, index) => {
                const searchDate = new Date(search.search_timestamp || search.timestamp);
                const truncatedQuery = truncateText(search.search_query || search.query, 60);
                const candidatesCount = search.actual_results || search.result_count || 0;

                return `
                    <div class="px-6 py-4 hover:bg-gray-50 transition-colors cursor-pointer history-row" data-search-id="${search.id}" data-query="${search.search_query || search.query}">
                        <div class="grid grid-cols-12 gap-4 items-center">
                            <!-- Job Description -->
                            <div class="col-span-4">
                                <div class="text-sm font-medium text-gray-900" title="${search.search_query || search.query}">
                                    ${truncatedQuery}
                                </div>
                                ${search.job_title ? `<div class="text-xs text-gray-500 mt-1">${search.job_title}</div>` : ''}
                            </div>
                            
                            <!-- Date & Time -->
                            <div class="col-span-2">
                                <div class="text-sm text-gray-900">${formatDate(searchDate)}</div>
                                <div class="text-xs text-gray-500">${formatTime(searchDate)}</div>
                            </div>
                            
                            <!-- Candidates Count -->
                            <div class="col-span-2">
                                <div class="flex items-center">
                                    <span class="text-sm font-medium text-gray-900">${candidatesCount}</span>
                                    <span class="text-xs text-gray-500 ml-1">candidates found</span>
                                </div>
                            </div>
                            
                            <!-- Top Results Preview -->
                            <div class="col-span-3">
                                <div class="space-y-1">
                                    ${search.top_results && search.top_results.length > 0 ?
                        search.top_results.slice(0, 3).map(result => `
                                            <div class="flex items-center justify-between bg-gray-50 rounded px-2 py-1">
                                                <div class="flex items-center space-x-2">
                                                    <div class="w-4 h-4 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center">
                                                        <span class="text-white font-bold text-xs">${result.name ? result.name.charAt(0).toUpperCase() : '?'}</span>
                                                    </div>
                                                    <span class="text-xs font-medium text-gray-700 truncate max-w-[80px]" title="${result.name || 'Unknown'}">
                                                        ${truncateText(result.name || 'Unknown', 12)}
                                                    </span>
                                                </div>
                                                <span class="text-xs font-bold text-green-600">${result.score || 0}%</span>
                                            </div>
                                        `).join('') :
                        '<span class="text-xs text-gray-400">No preview available</span>'
                    }
                                    ${search.top_results && search.top_results.length > 3 ?
                        `<div class="text-xs text-gray-500 text-center">+${search.top_results.length - 3} more candidates</div>` : ''
                    }
                                </div>
                            </div>
                            
                            <!-- Actions -->
                            <div class="col-span-1 text-center">
                                <div class="flex items-center justify-center space-x-1">
                                    <button class="view-search p-1.5 text-blue-600 hover:bg-blue-50 rounded transition-colors" 
                                            data-search-id="${search.id}" data-query="${search.search_query || search.query}"
                                            title="View Results">
                                        <i class="fas fa-eye text-xs"></i>
                                    </button>
                                    <button class="delete-search p-1.5 text-red-600 hover:bg-red-50 rounded transition-colors" 
                                            data-search-id="${search.id}"
                                            title="Delete Search">
                                        <i class="fas fa-trash text-xs"></i>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');

            // Re-attach event listeners after rendering
            attachHistoryEventListeners();
        }
    }

    // Make loadSavedSearch available globally for the onclick attribute in HTML
    window.loadSavedSearch = async function (searchId, query) {
        try {
            // Get the search resumes link element
            const searchResumesLinkElement = document.getElementById('search-resumes-link');

            // Switch to search page
            if (searchResumesLinkElement) {
                setActiveLink(searchResumesLinkElement);
            }
            loadPage('searchResumes');

            // Wait for page to load
            setTimeout(async () => {
                // Show loading
                showLoadingMessage();

                // Animate to results view
                animateChatToResults();

                // Fetch saved results
                const response = await fetch(`/api/search-results/${searchId}`);
                const data = await response.json();

                if (data.success && data.results) {
                    // Hide loading
                    hideLoadingMessage();

                    // Transform the saved data to match the expected format
                    const transformedResults = data.results.map(result => {
                        // Ensure the result has the correct structure
                        // The saved data already has gemini_analysis, but we need to ensure it's in the right format
                        return {
                            id: result.id,
                            document_name: result.document_name,
                            relevance_score: result.relevance_score || 0,
                            file_path: result.file_path,
                            gemini_analysis: result.gemini_analysis || {
                                success: false,
                                match_score: 0,
                                hr_scorecard: null
                            },
                            analysis_type: result.analysis_type || 'comprehensive_hr_scorecard'
                        };
                    });

                    // Display results using the existing function
                    const resultsData = {
                        results: transformedResults,
                        total_results: data.total_results || transformedResults.length,
                        query: query
                    };

                    generateEnhancedResults(resultsData);

                    // Hide the bottom chat container when viewing saved results
                    const bottomChatContainer = document.getElementById('bottom-chat-container');
                    if (bottomChatContainer) {
                        bottomChatContainer.style.display = 'none';
                    }

                    // Add user message to show the query
                    addUserMessage(query);

                    // Show notification that results are loaded from history
                    showFinalResultsNotification();
                } else {
                    hideLoadingMessage();
                    // Show error message
                    const resultsContainer = document.getElementById('results-container');
                    if (resultsContainer) {
                        resultsContainer.innerHTML = `
                            <div class="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
                                <i class="fas fa-exclamation-triangle text-red-500 text-2xl mb-2"></i>
                                <h3 class="text-lg font-semibold text-red-800 mb-2">Failed to Load Search Results</h3>
                                <p class="text-red-700 text-sm">Unable to retrieve the saved search results. Please try again.</p>
                            </div>
                        `;
                    }
                }
            }, 300);
        } catch (error) {
            console.error('Error loading saved search:', error);
            hideLoadingMessage();
            // Show error message
            const resultsContainer = document.getElementById('results-container');
            if (resultsContainer) {
                resultsContainer.innerHTML = `
                    <div class="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
                        <i class="fas fa-exclamation-triangle text-red-500 text-2xl mb-2"></i>
                        <h3 class="text-lg font-semibold text-red-800 mb-2">Error Loading Results</h3>
                        <p class="text-red-700 text-sm">${error.message || 'An unexpected error occurred'}</p>
                    </div>
                `;
            }
        }
    }

    function saveSearchToHistory(query, resultCount, topResults) {
        const searchEntry = {
            query: query,
            timestamp: new Date().toISOString(),
            resultCount: resultCount,
            topResults: topResults.slice(0, 4) // Save top 4 results for preview
        };

        // Add to beginning of array (most recent first)
        searchHistory.unshift(searchEntry);

        // Keep only last 20 searches
        if (searchHistory.length > 20) {
            searchHistory = searchHistory.slice(0, 20);
        }

        // Save to localStorage
        localStorage.setItem('searchHistory', JSON.stringify(searchHistory));
    }

    // New dashboard initialization function
    function initializeDashboard() {
        // Single real-data dashboard for all roles (admin-only fake template removed)
        const userDash = document.getElementById('user-dashboard');
        if (!userDash) {
            console.error('Dashboard element not found');
            return;
        }
        userDash.style.display = 'block';
        showDashboardLoadingState();

        setTimeout(() => {
            if (window.currentUser && window.currentUser.user_type) {
                console.log('Loading dashboard for user type:', window.currentUser.user_type);
                initializeUserDashboard();
            } else {
                setTimeout(() => {
                    if (window.currentUser) {
                        initializeUserDashboard();
                    } else {
                        console.log('No user data; loading dashboard with defaults');
                        initializeUserDashboard();
                    }
                }, 1000);
            }
        }, 100);
    }

    // initializeDashboardCharts: stub. Admin-only fake-data charts removed;
    // dashboard now uses real /api/dashboard-stats data via initializeUserDashboard.
    function initializeDashboardCharts() { /* no-op */ }

    // Show loading state for charts
    function showChartsLoadingState() {
        const chartContainers = document.querySelectorAll('.chart-container');
        chartContainers.forEach(container => {
            // Save original content
            container.dataset.originalContent = container.innerHTML;

            // Replace with loading animation
            container.innerHTML = `
                <div class="flex items-center justify-center h-full min-h-[300px]">
                    <div class="animate-pulse flex flex-col items-center">
                        <div class="rounded-full bg-gray-200 h-24 w-24 mb-4"></div>
                        <div class="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
                        <div class="h-4 bg-gray-200 rounded w-1/2"></div>
                    </div>
                </div>
            `;
        });
    }

    // Remove loading state from charts
    function removeChartsLoadingState() {
        const chartContainers = document.querySelectorAll('.chart-container');
        chartContainers.forEach(container => {
            // If there was no original content (first load), just clear the loading state
            if (!container.dataset.originalContent) {
                container.classList.remove('animate-pulse');
            }
        });
    }

    function initializeUploadPage() {
        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('file-input');
        const browseFiles = document.getElementById('browse-files');
        const uploadQueue = document.getElementById('upload-queue');
        const startUpload = document.getElementById('start-upload');
        const clearQueue = document.getElementById('clear-queue');

        let selectedFiles = [];

        // Load configuration and pre-populate fields
        loadConfigAndPopulateFields();

        // File input handling
        browseFiles.addEventListener('click', (e) => {
            e.stopPropagation();
            fileInput.click();
        });

        fileInput.addEventListener('change', (e) => {
            handleFiles(e.target.files);
            // Reset value so picking the same file twice still fires `change`.
            e.target.value = '';
        });

        // Clicking anywhere on the drop zone also opens the file picker --
        // the `cursor-pointer` class advertises this behaviour.
        dropZone.addEventListener('click', () => {
            fileInput.click();
        });

        // Drag and drop handling
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('border-blue-400', 'bg-blue-50');
        });

        dropZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            dropZone.classList.remove('border-blue-400', 'bg-blue-50');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('border-blue-400', 'bg-blue-50');
            handleFiles(e.dataTransfer.files);
        });

        // Clear queue
        clearQueue.addEventListener('click', () => {
            selectedFiles = [];
            updateUploadQueue();
        });

        // Start upload
        startUpload.addEventListener('click', () => {
            if (selectedFiles.length > 0) {
                const uploadFolder = document.getElementById('upload-folder').value;

                // Check if GCS is configured
                fetch('/api/gcs-status')
                    .then(response => response.json())
                    .then(data => {
                        if (!data.configured) {
                            showCredentialsModal();
                        } else {
                            performUpload(uploadFolder);
                        }
                    })
                    .catch(error => {
                        console.error('Error checking GCS status:', error);
                        showCredentialsModal();
                    });
            }
        });

        function loadConfigAndPopulateFields() {
            fetch('/api/gcs-status')
                .then(response => response.json())
                .then(data => {
                    if (data.bucket_name) {
                        document.getElementById('bucket-name').value = data.bucket_name;
                    }
                    if (data.default_folder) {
                        document.getElementById('upload-folder').value = data.default_folder;
                    } else {
                        // Fallback to default if not configured
                        document.getElementById('upload-folder').value = 'resume/';
                    }

                    // Configuration is handled automatically, no UI updates needed
                })
                .catch(error => {
                    console.error('Error loading configuration:', error);
                    // Set fallback folder path if config fails to load
                    document.getElementById('upload-folder').value = 'resume/';
                });
        }

        function handleFiles(files) {
            // Per-file limit aligned with backend MAX_FILE_SIZE (main.py).
            const maxFileSize = 10 * 1024 * 1024; // 10MB in bytes

            for (let file of files) {
                if (!file.name.match(/\.(pdf|doc|docx)$/i)) {
                    alert(`File ${file.name} is not supported. Only PDF, DOC, and DOCX files are allowed.`);
                    continue;
                }

                // Check file size
                if (file.size > maxFileSize) {
                    const fileSizeMB = (file.size / (1024 * 1024)).toFixed(1);
                    const maxSizeMB = (maxFileSize / (1024 * 1024)).toFixed(0);
                    alert(`File ${file.name} is too large (${fileSizeMB}MB). Maximum file size allowed is ${maxSizeMB}MB.`);
                    continue;
                }

                selectedFiles.push({
                    file: file,
                    id: Date.now() + Math.random(),
                    status: 'pending',
                    progress: 0
                });
            }
            updateUploadQueue();
        }

        async function performUpload(uploadFolder) {
            // Adaptive batch size configuration
            let currentBatchSize = 50; // Start with 50 files per batch
            const MIN_BATCH_SIZE = 1; // Minimum batch size
            const MAX_BATCH_SIZE_MB = 32; // 32MB per batch
            const batchSizeHistory = []; // Track successful batch sizes

            // Show overall progress bar
            const progressContainer = document.getElementById('overall-progress-container');
            const progressBar = document.getElementById('overall-progress-bar');
            const progressText = document.getElementById('overall-progress-text');
            const batchProgressText = document.getElementById('batch-progress-text');
            const filesProgressText = document.getElementById('files-progress-text');

            progressContainer.classList.remove('hidden');
            progressBar.style.width = '0%';
            progressText.textContent = '0%';
            batchProgressText.textContent = `Initializing...`;
            filesProgressText.textContent = `0/${selectedFiles.length} files queued`;

            let totalSuccessful = 0;
            let totalFailed = 0;
            let batchResults = [];
            let remainingFiles = [...selectedFiles]; // Copy of files to process
            let batchNumber = 0;
            let totalBatches = 0; // Will be calculated dynamically

            console.log(`🚀 Starting adaptive batch upload with initial batch size: ${currentBatchSize}`);

            // Process files with adaptive batch sizing
            while (remainingFiles.length > 0) {
                batchNumber++;

                // Create current batch with current batch size
                const currentBatch = createBatches(remainingFiles, currentBatchSize, MAX_BATCH_SIZE_MB)[0];
                if (!currentBatch || currentBatch.length === 0) {
                    console.error('? Unable to create batch - breaking upload loop');
                    break;
                }

                console.log(`📤 Uploading batch ${batchNumber} (${currentBatch.length} files, batch size: ${currentBatchSize})`);

                // Update progress UI
                const completedFiles = selectedFiles.length - remainingFiles.length;
                const overallProgress = (completedFiles / selectedFiles.length) * 100;
                progressBar.style.width = `${overallProgress}%`;
                progressText.textContent = `${Math.round(overallProgress)}%`;
                batchProgressText.textContent = `Batch ${batchNumber} (${currentBatch.length} files)`;

                // Update UI to show current batch uploading
                currentBatch.forEach(fileItem => {
                    fileItem.status = 'uploading';
                    fileItem.progress = 0;
                    fileItem.batchInfo = `Batch ${batchNumber} (Size: ${currentBatchSize})`;
                });
                updateUploadQueue();

                let batchSuccess = false;

                try {
                    const batchResult = await uploadBatch(currentBatch, uploadFolder, batchNumber, '8');
                    batchResults.push(batchResult);
                    batchSuccess = true;

                    // Update individual file statuses based on batch result
                    if (batchResult.results) {
                        batchResult.results.forEach((result, index) => {
                            if (index < currentBatch.length) {
                                currentBatch[index].status = result.success ? 'completed' : 'failed';
                                currentBatch[index].progress = 100;
                                currentBatch[index].error = result.error;
                                currentBatch[index].gcs_path = result.gcs_path;
                                currentBatch[index].batchInfo = `Batch ${batchNumber} · ${result.success ? 'Success' : 'Failed'}`;
                            }
                        });

                        const successful = batchResult.results.filter(r => r.success).length;
                        const failed = batchResult.results.filter(r => !r.success).length;
                        totalSuccessful += successful;
                        totalFailed += failed;

                        // Update files progress
                        const totalCompleted = totalSuccessful + totalFailed;
                        filesProgressText.textContent = `${totalCompleted}/${selectedFiles.length} files completed`;
                    }

                    // Remove successfully processed files from remaining files
                    remainingFiles = remainingFiles.filter(file => !currentBatch.includes(file));

                    // Track successful batch size
                    batchSizeHistory.push(currentBatchSize);
                    console.log(`? Batch ${batchNumber} completed successfully with size ${currentBatchSize}`);

                    // Optionally increase batch size if we've had consecutive successes
                    if (batchSizeHistory.length >= 2 &&
                        batchSizeHistory.slice(-2).every(size => size === currentBatchSize) &&
                        currentBatchSize < 50) {
                        currentBatchSize = Math.min(currentBatchSize * 2, 50);
                        console.log(`⬆️ Increasing batch size to ${currentBatchSize} after consecutive successes`);
                    }

                } catch (error) {
                    console.error(`? Batch ${batchNumber} failed (size: ${currentBatchSize}):`, error);
                    batchSuccess = false;

                    // Mark all files in this batch as failed temporarily
                    currentBatch.forEach(fileItem => {
                        fileItem.status = 'retrying';
                        fileItem.error = error.message || 'Batch upload failed - retrying with smaller batch';
                        fileItem.batchInfo = `Batch ${batchNumber} · Retrying`;
                    });
                    updateUploadQueue();

                    // Implement adaptive batch size reduction
                    if (currentBatchSize > MIN_BATCH_SIZE) {
                        // Reduce batch size (halve it, but ensure it's at least 1)
                        const newBatchSize = Math.max(Math.floor(currentBatchSize / 2), MIN_BATCH_SIZE);
                        console.log(`⬇️ Reducing batch size from ${currentBatchSize} to ${newBatchSize}`);
                        currentBatchSize = newBatchSize;

                        // Reset batch info for retry
                        currentBatch.forEach(fileItem => {
                            fileItem.status = 'pending';
                            fileItem.error = null;
                            fileItem.batchInfo = `Retrying with smaller batch (${currentBatchSize})`;
                        });
                        updateUploadQueue();

                        // Don't remove files from remaining files - they'll be retried
                        console.log(`🔄 Retrying failed batch with smaller size: ${currentBatchSize}`);

                        // Small delay before retry
                        await new Promise(resolve => setTimeout(resolve, 2000));
                        continue; // Retry with smaller batch size
                    } else {
                        // Even minimum batch size failed - mark files as failed
                        console.error(`? Batch failed even with minimum size (${MIN_BATCH_SIZE}) - marking files as failed`);
                        currentBatch.forEach(fileItem => {
                            fileItem.status = 'failed';
                            fileItem.error = error.message || 'Upload failed even with minimum batch size';
                            fileItem.batchInfo = `Batch ${batchNumber} · Failed`;
                        });
                        totalFailed += currentBatch.length;

                        // Remove failed files from remaining files
                        remainingFiles = remainingFiles.filter(file => !currentBatch.includes(file));

                        // Update files progress
                        const totalCompleted = totalSuccessful + totalFailed;
                        filesProgressText.textContent = `${totalCompleted}/${selectedFiles.length} files completed`;
                    }
                }

                updateUploadQueue();

                // Small delay between batches to prevent overwhelming the server
                if (remainingFiles.length > 0) {
                    await new Promise(resolve => setTimeout(resolve, 1000));
                }
            }

            // Complete progress bar
            progressBar.style.width = '100%';
            progressText.textContent = '100%';
            batchProgressText.textContent = `Completed: ${batchNumber} adaptive batches`;

            // Hide progress bar after 3 seconds
            setTimeout(() => {
                progressContainer.classList.add('hidden');
            }, 3000);

            // Update final stats
            const totalUploaded = document.getElementById('total-uploaded');
            const successfulUploads = document.getElementById('successful-uploads');
            const failedUploads = document.getElementById('failed-uploads');

            totalUploaded.textContent = parseInt(totalUploaded.textContent) + selectedFiles.length;
            successfulUploads.textContent = parseInt(successfulUploads.textContent) + totalSuccessful;
            failedUploads.textContent = parseInt(failedUploads.textContent) + totalFailed;

            // Show adaptive upload summary message
            const finalBatchSize = currentBatchSize;
            const usedAdaptiveStrategy = batchSizeHistory.some(size => size !== 50);
            let strategyInfo = '';

            if (usedAdaptiveStrategy) {
                const uniqueBatchSizes = [...new Set(batchSizeHistory)].sort((a, b) => b - a);
                strategyInfo = ` (Adaptive strategy used: ${uniqueBatchSizes.join('?')} files per batch)`;
            } else {
                strategyInfo = ` (Maintained optimal batch size of 50)`;
            }

            const message = `Upload completed! ${totalSuccessful} successful, ${totalFailed} failed across ${batchNumber} batches${strategyInfo}`;
            if (totalSuccessful > 0) {
                showLimitNotification(message, totalFailed > 0 ? 'warning' : 'success');
            } else if (totalFailed > 0) {
                showLimitNotification(`All uploads failed: ${message}`, 'error');
            }
        }

        function createBatches(files, maxFilesPerBatch, maxBatchSizeMB) {
            const batches = [];
            let currentBatch = [];
            let currentBatchSize = 0;
            const maxBatchSizeBytes = maxBatchSizeMB * 1024 * 1024;

            for (const fileItem of files) {
                const fileSize = fileItem.file.size;

                // Check if adding this file would exceed batch limits
                if (currentBatch.length >= maxFilesPerBatch ||
                    (currentBatchSize + fileSize > maxBatchSizeBytes && currentBatch.length > 0)) {
                    // Start new batch
                    if (currentBatch.length > 0) {
                        batches.push(currentBatch);
                    }
                    currentBatch = [];
                    currentBatchSize = 0;
                }

                currentBatch.push(fileItem);
                currentBatchSize += fileSize;
            }

            // Don't forget the last batch
            if (currentBatch.length > 0) {
                batches.push(currentBatch);
            }

            return batches;
        }

        async function uploadBatch(batch, uploadFolder, batchNumber, totalBatches) {
            const formData = new FormData();

            batch.forEach(fileItem => {
                formData.append('files', fileItem.file);
            });
            formData.append('folder_path', uploadFolder);
            formData.append('batch_info', `${batchNumber}/${totalBatches}`);

            const response = await fetch('/api/upload-files', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json();
                if (response.status === 413) {
                    // Handle structured 413 error from middleware
                    const maxSizeMB = errorData.max_size_mb || 100;
                    const receivedSizeMB = errorData.received_size_mb || 'unknown';
                    throw new Error(`Batch too large: ${receivedSizeMB}MB exceeds limit of ${maxSizeMB}MB`);
                }
                throw new Error(errorData.detail || `Batch ${batchNumber} upload failed`);
            }

            return await response.json();
        }

        function showLimitNotification(message, type = 'error') {
            // Create notification element
            const notification = document.createElement('div');
            notification.className = `fixed top-4 right-4 z-50 max-w-md p-4 rounded-lg shadow-lg border-l-4 ${type === 'error' ? 'bg-red-50 border-red-400 text-red-800' :
                type === 'warning' ? 'bg-yellow-50 border-yellow-400 text-yellow-800' : 'bg-blue-50 border-blue-400 text-blue-800'
                }`;

            notification.innerHTML = `
                <div class="flex items-start">
                    <div class="flex-shrink-0">
                        <i class="fas fa-${type === 'error' ? 'exclamation-circle' :
                    type === 'warning' ? 'exclamation-triangle' : 'info-circle'
                } text-lg"></i>
                    </div>
                    <div class="ml-3">
                        <h3 class="text-sm font-medium">${type === 'error' ? 'Upload Limit Reached' :
                    type === 'warning' ? 'Warning' : 'Information'
                }</h3>
                        <p class="mt-1 text-sm">${message}</p>
                    </div>
                    <div class="ml-auto pl-3">
                        <button class="inline-flex rounded-md p-1.5 hover:bg-gray-100 focus:outline-none" onclick="this.parentElement.parentElement.parentElement.remove()">
                            <i class="fas fa-times text-sm"></i>
                        </button>
                    </div>
                </div>
            `;

            // Add to page
            document.body.appendChild(notification);

            // Auto remove after 8 seconds
            setTimeout(() => {
                if (notification.parentElement) {
                    notification.remove();
                }
            }, 8000);
        }

        function updateUploadQueue() {
            if (selectedFiles.length === 0) {
                uploadQueue.innerHTML = `
                    <div class="text-center text-gray-500 py-8">
                        <i class="fas fa-inbox text-4xl text-gray-300 mb-2"></i>
                        <p>No files selected. Drop files or browse to add them to the queue.</p>
                    </div>
                `;
                startUpload.disabled = true;
            } else {
                // Calculate batch information for display with adaptive sizing
                const INITIAL_BATCH_SIZE = 50; // Start with 50 files per batch
                const MAX_BATCH_SIZE_MB = 32; // 32MB per batch
                const estimatedBatches = Math.ceil(selectedFiles.length / INITIAL_BATCH_SIZE);

                uploadQueue.innerHTML = `
                    <div class="mb-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
                        <div class="flex items-center justify-between text-sm">
                            <span class="text-blue-700 font-medium">
                                <i class="fas fa-layer-group mr-2"></i>
                                Adaptive Upload Strategy: Starting with ${INITIAL_BATCH_SIZE} files per batch
                                (Auto-adjusts: 50→25→10→5→1 on failures)
                            </span>
                            <span class="text-blue-600">${selectedFiles.length} total files</span>
                        </div>
                        <div class="mt-2 text-xs text-blue-600">
                            <i class="fas fa-info-circle mr-1"></i>
                            System will automatically reduce batch size if uploads fail, then increase back to 50 after successes
                        </div>
                    </div>
                    ${selectedFiles.map((fileItem, index) => {
                    const statusIcon = getStatusIcon(fileItem.status);
                    const statusColor = getStatusColor(fileItem.status);

                    return `
                        <div class="flex items-center justify-between p-3 border border-gray-200 rounded-lg mb-2">
                            <div class="flex items-center space-x-3">
                                <div class="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center">
                                    <i class="fas fa-file-${getFileIcon(fileItem.file.name)} text-gray-600"></i>
                                </div>
                                <div>
                                    <p class="text-sm font-medium text-gray-900">${fileItem.file.name}</p>
                                    <div class="flex items-center space-x-2 text-xs text-gray-500">
                                        <span>${formatFileSize(fileItem.file.size)}</span>
                                        <span class="text-gray-300">·</span>
                                        <span class="text-blue-600">Adaptive Batching</span>
                                        ${fileItem.batchInfo ? `<span class="text-gray-300">·</span><span class="${statusColor}">${fileItem.batchInfo}</span>` : ''}
                                    </div>
                                </div>
                            </div>
                            <div class="flex items-center space-x-3">
                                <div class="flex items-center space-x-2">
                                    <span class="text-xs ${statusColor} capitalize">
                                        ${statusIcon} ${fileItem.status}
                                    </span>
                                    ${fileItem.status === 'uploading' ? `
                                        <div class="w-20 bg-gray-200 rounded-full h-2">
                                            <div class="bg-blue-600 h-2 rounded-full transition-all duration-300" style="width: ${fileItem.progress}%"></div>
                                        </div>
                                    ` : ''}
                                    ${fileItem.error ? `
                                        <div class="text-xs text-red-600 max-w-xs truncate" title="${fileItem.error}">
                                            ${fileItem.error}
                                        </div>
                                    ` : ''}
                                </div>
                                <button class="text-red-600 hover:text-red-800" onclick="removeFile('${fileItem.id}')">
                                    <i class="fas fa-trash text-xs"></i>
                                </button>
                            </div>
                        </div>
                    `;
                }).join('')}
                `;
                startUpload.disabled = false;
            }
        }

        function getStatusIcon(status) {
            switch (status) {
                case 'completed': return '<i class="fas fa-check-circle"></i>';
                case 'failed': return '<i class="fas fa-exclamation-circle"></i>';
                case 'uploading': return '<i class="fas fa-spinner fa-spin"></i>';
                case 'retrying': return '<i class="fas fa-redo fa-spin"></i>';
                default: return '<i class="fas fa-clock"></i>';
            }
        }

        function getStatusColor(status) {
            switch (status) {
                case 'completed': return 'text-green-600';
                case 'failed': return 'text-red-600';
                case 'uploading': return 'text-blue-600';
                case 'retrying': return 'text-yellow-600';
                default: return 'text-gray-500';
            }
        }

        function getFileIcon(filename) {
            const ext = filename.split('.').pop().toLowerCase();
            switch (ext) {
                case 'pdf': return 'pdf';
                case 'doc':
                case 'docx': return 'word';
                default: return 'alt';
            }
        }

        function formatFileSize(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }

        function showCredentialsModal() {
            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
            modal.innerHTML = `
                <div class="bg-white rounded-lg p-6 max-w-md w-full mx-4">
                    <h3 class="text-lg font-semibold mb-4">Configure Google Cloud Storage</h3>
                    <p class="text-sm text-gray-600 mb-4">Please provide your bucket name to enable file uploads. Credentials are loaded from local file.</p>
                    
                    <div class="space-y-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Bucket Name</label>
                            <input type="text" id="modal-bucket-name" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="your-bucket-name">
                        </div>
                        <div class="text-xs text-gray-500">
                            <i class="fas fa-info-circle mr-1"></i>
                            Credentials file: service-account.json
                        </div>
                    </div>
                    
                    <div class="flex justify-end space-x-3 mt-6">
                        <button id="cancel-config" class="px-4 py-2 text-gray-600 hover:text-gray-800">Cancel</button>
                        <button id="save-config" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">Configure</button>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);

            document.getElementById('cancel-config').addEventListener('click', () => {
                document.body.removeChild(modal);
            });

            document.getElementById('save-config').addEventListener('click', () => {
                const bucketName = document.getElementById('modal-bucket-name').value;

                if (!bucketName) {
                    alert('Please provide bucket name.');
                    return;
                }

                configureGCS(bucketName, modal);
            });
        }

        function configureGCS(bucketName, modal) {
            const formData = new FormData();
            formData.append('bucket_name', bucketName);

            fetch('/api/configure-gcs', {
                method: 'POST',
                body: formData
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('bucket-name').value = bucketName;
                        document.body.removeChild(modal);
                        alert('Google Cloud Storage configured successfully!');
                        performUpload(document.getElementById('upload-folder').value);
                    } else {
                        alert('Configuration failed: ' + (data.detail || 'Unknown error'));
                    }
                })
                .catch(error => {
                    console.error('Error configuring GCS:', error);
                    alert('Configuration failed. Please check your bucket name and ensure credentials file exists.');
                });
        }

        // Make removeFile function global
        window.removeFile = function (fileId) {
            // ``fileId`` arrives as a string from inline onclick attributes while
            // ``file.id`` is stored as a number (Date.now() + Math.random()).
            // Compare as strings so identifiers actually match.
            const key = String(fileId);
            selectedFiles = selectedFiles.filter(file => String(file.id) !== key);
            updateUploadQueue();
        };

        // Tab switching functionality
        const fileUploadTab = document.getElementById('file-upload-tab');
        const emailScrapeTab = document.getElementById('email-scrape-tab');
        const fileUploadSection = document.getElementById('file-upload-section');
        const emailScrapeSection = document.getElementById('email-scrape-section');

        fileUploadTab.addEventListener('click', () => {
            // Switch to file upload tab
            fileUploadTab.classList.add('bg-blue-600', 'text-white');
            fileUploadTab.classList.remove('bg-gray-200', 'text-gray-700');
            emailScrapeTab.classList.add('bg-gray-200', 'text-gray-700');
            emailScrapeTab.classList.remove('bg-blue-600', 'text-white');

            fileUploadSection.classList.remove('hidden');
            emailScrapeSection.classList.add('hidden');
        });

        emailScrapeTab.addEventListener('click', () => {
            // Switch to email scraping tab
            emailScrapeTab.classList.add('bg-blue-600', 'text-white');
            emailScrapeTab.classList.remove('bg-gray-200', 'text-gray-700');
            fileUploadTab.classList.add('bg-gray-200', 'text-gray-700');
            fileUploadTab.classList.remove('bg-blue-600', 'text-white');

            emailScrapeSection.classList.remove('hidden');
            fileUploadSection.classList.add('hidden');
        });

        // Password visibility toggle
        const togglePasswordBtn = document.getElementById('toggle-password');
        const passwordInput = document.getElementById('email-password');

        togglePasswordBtn.addEventListener('click', () => {
            const isPassword = passwordInput.type === 'password';
            passwordInput.type = isPassword ? 'text' : 'password';

            const icon = togglePasswordBtn.querySelector('i');
            icon.classList.toggle('fa-eye');
            icon.classList.toggle('fa-eye-slash');
        });

        // Email scraping functionality
        const startEmailScrapeBtn = document.getElementById('start-email-scrape');

        startEmailScrapeBtn.addEventListener('click', async () => {
            const emailProvider = document.getElementById('email-provider').value;
            const emailAddress = document.getElementById('email-address').value;
            const emailPassword = document.getElementById('email-password').value;
            const emailLimit = document.getElementById('email-limit').value;

            // Validate inputs
            if (!emailProvider) {
                showLimitNotification('Please select an email provider', 'error');
                return;
            }

            if (!emailAddress) {
                showLimitNotification('Please enter your email address', 'error');
                return;
            }

            if (!emailPassword) {
                showLimitNotification('Please enter your email password', 'error');
                return;
            }

            // Disable button and show loading state
            startEmailScrapeBtn.disabled = true;
            startEmailScrapeBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Scraping Emails...';

            try {
                // Perform email scraping
                const formData = new FormData();
                formData.append('scrape_email', 'true');
                formData.append('email_provider', emailProvider);
                formData.append('email_address', emailAddress);
                formData.append('email_password', emailPassword);
                formData.append('email_limit', emailLimit);

                const uploadFolder = document.getElementById('upload-folder').value || 'resume/';
                formData.append('folder_path', uploadFolder);

                const response = await fetch('/api/upload-files', {
                    method: 'POST',
                    body: formData
                });

                let result;
                try {
                    result = await response.json();
                } catch (_) {
                    result = {};
                }

                if (response.ok) {
                    const batchStats = result.batch_stats || {};
                    const emailStats = result.email_stats || {};
                    const totalAttachments =
                        Number(emailStats.total_attachments) ||
                        Number(batchStats.total) || 0;
                    const successfulCount =
                        Number(emailStats.successful_uploads) ||
                        Number(batchStats.successful) || 0;
                    const failedCount =
                        Number(emailStats.failed_uploads) ||
                        Number(batchStats.failed) || 0;
                    const totalEmails = Number(emailStats.total_emails) || 0;

                    if (totalAttachments === 0) {
                        showLimitNotification(
                            result.message || 'No resume attachments were found in the scanned emails.',
                            'info'
                        );
                    } else {
                        showLimitNotification(
                            `Processed ${successfulCount}/${totalAttachments} attachment(s) from ${totalEmails} email(s)` +
                                (failedCount > 0 ? ` (${failedCount} failed)` : ''),
                            failedCount > 0 ? 'warning' : 'success'
                        );
                    }

                    // Clear the form
                    document.getElementById('email-provider').value = '';
                    document.getElementById('email-address').value = '';
                    document.getElementById('email-password').value = '';
                    document.getElementById('email-limit').value = '100';

                    // Update stats
                    const totalUploaded = document.getElementById('total-uploaded');
                    const successfulUploads = document.getElementById('successful-uploads');
                    if (totalUploaded) {
                        totalUploaded.textContent = parseInt(totalUploaded.textContent || '0') + totalAttachments;
                    }
                    if (successfulUploads) {
                        successfulUploads.textContent = parseInt(successfulUploads.textContent || '0') + successfulCount;
                    }

                } else {
                    const msg = (result && (result.detail || result.message)) ||
                        `Failed to scrape emails (HTTP ${response.status})`;
                    showLimitNotification(msg, 'error');
                }

            } catch (error) {
                console.error('Error scraping emails:', error);
                showLimitNotification('An error occurred while scraping emails', 'error');
            } finally {
                // Re-enable button
                startEmailScrapeBtn.disabled = false;
                startEmailScrapeBtn.innerHTML = '<i class="fas fa-envelope-open-text mr-2"></i>Start Email Scraping';
            }
        });
    }

    // Navigation event listeners
    dashboardLink.addEventListener('click', (e) => {
        e.preventDefault();
        setActiveLink(dashboardLink);
        loadPage('dashboard');
    });

    searchResumesLink.addEventListener('click', (e) => {
        e.preventDefault();
        setActiveLink(searchResumesLink);
        loadPage('searchResumes');
    });

    if (jdBuilderLink) {
        jdBuilderLink.addEventListener('click', (e) => {
            e.preventDefault();
            setActiveLink(jdBuilderLink);
            loadPage('jdBuilder');
        });
    }

    if (vectorSearchLink) {
        vectorSearchLink.addEventListener('click', (e) => {
            e.preventDefault();
            setActiveLink(vectorSearchLink);
            loadPage('vectorSearch');
        });
    }

    historyLink.addEventListener('click', (e) => {
        e.preventDefault();
        setActiveLink(historyLink);
        loadPage('history');
    });

    uploadFilesLink.addEventListener('click', (e) => {
        e.preventDefault();
        setActiveLink(uploadFilesLink);
        loadPage('uploadFiles');
    });

    settingsLink.addEventListener('click', (e) => {
        e.preventDefault();
        setActiveLink(settingsLink);
        loadPage('settings');
    });

    // Make setActiveLink available globally
    window.setActiveLink = function (activeLink) {
        // Get all navigation links
        const navLinks = document.querySelectorAll('.nav-link');

        // Remove active class from all links
        navLinks.forEach(link => {
            if (link) {
                link.classList.remove('active');
            }
        });

        // Add active class to the selected link
        if (activeLink) {
            activeLink.classList.add('active');
        }
    }

    // Load initial page
    setActiveLink(vectorSearchLink);
    loadPage('vectorSearch');

    // Global function to show analysis modal
    window.showAnalysisModal = function (candidateName, analysisData) {
        const esc = window.escapeHtml || ((value) => {
            const div = document.createElement('div');
            div.textContent = value == null ? '' : String(value);
            return div.innerHTML;
        });
        const sanitize = window.sanitizeGeneratedHtml || ((html) => html || '');
        // Create modal HTML
        const modalHTML = `
            <div id="analysisModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                <div class="bg-white rounded-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
                    <!-- Modal Header -->
                    <div class="sticky top-0 bg-white border-b border-gray-200 p-6 rounded-t-xl">
                        <div class="flex items-center justify-between">
                            <div>
                                <h2 class="text-xl font-bold text-gray-900">Complete AI Analysis</h2>
                                <p class="text-gray-600 text-sm">${esc(candidateName)}</p>
                            </div>
                            <button onclick="closeAnalysisModal()" class="w-8 h-8 bg-gray-100 hover:bg-gray-200 rounded-full flex items-center justify-center transition-colors">
                                <i class="fas fa-times text-gray-600"></i>
                            </button>
                        </div>
                    </div>
                    
                    <!-- Modal Content -->
                    <div class="p-6">
                        ${sanitize(generateAnalysisContent(analysisData))}
                    </div>
                </div>
            </div>
        `;

        // Add modal to body
        document.body.insertAdjacentHTML('beforeend', modalHTML);

        // Prevent body scroll
        document.body.style.overflow = 'hidden';
    };

    // Global function to close analysis modal
    window.closeAnalysisModal = function () {
        const modal = document.getElementById('analysisModal');
        if (modal) {
            modal.remove();
            document.body.style.overflow = 'auto';
        }
    };

    // Function to generate analysis content - supports both basic and HR scorecard formats
    function generateAnalysisContent(analysisData) {
        // Check if we have HR scorecard data
        if (analysisData.hr_scorecard) {
            return generateHRScorecardContent(analysisData);
        }

        // Fallback to basic analysis
        const data = analysisData.analysis_json;

        if (!data) {
            return `
                <div class="text-center py-8">
                    <div class="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
                        <i class="fas fa-exclamation-triangle text-gray-400 text-2xl"></i>
                    </div>
                    <h3 class="text-lg font-medium text-gray-900 mb-2">Analysis Not Available</h3>
                    <p class="text-gray-600">The structured analysis data is not available for this candidate.</p>
                    <div class="mt-4 p-4 bg-gray-50 rounded-lg text-left">
                        <h4 class="font-medium text-gray-900 mb-2">Raw Analysis:</h4>
                        <div class="text-sm text-gray-700 whitespace-pre-line max-h-64 overflow-y-auto">
                            ${analysisData.analysis || 'No analysis available'}
                        </div>
                    </div>
                </div>
            `;
        }

        return `
            <!-- Candidate Information -->
            <div class="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-6 mb-6">
                <div class="flex items-center space-x-4 mb-4">
                    <div class="w-16 h-16 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center text-white font-bold text-2xl">
                        ${data.candidate_name?.charAt(0).toUpperCase() || 'C'}
                    </div>
                    <div>
                        <h3 class="text-xl font-bold text-gray-900">${data.candidate_name || 'Unknown Candidate'}</h3>
                        <p class="text-gray-600 font-medium">${data.current_role || 'Not specified'}</p>
                        <p class="text-gray-500">${data.location || 'Location not specified'}</p>
                    </div>
                    <div class="ml-auto text-center">
                        <div class="bg-green-100 border-2 border-green-300 rounded-xl p-4">
                            <div class="text-3xl font-bold text-green-700">${analysisData.match_score}%</div>
                            <div class="text-sm text-green-600 font-medium">MATCH SCORE</div>
                        </div>
                    </div>
                </div>
                
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                    <div>
                        <span class="text-gray-600">Email:</span>
                        <p class="font-medium text-gray-900">${data.email || 'Not available'}</p>
                    </div>
                    <div>
                        <span class="text-gray-600">Phone:</span>
                        <p class="font-medium text-gray-900">${data.phone || 'Not available'}</p>
                    </div>
                    <div>
                        <span class="text-gray-600">Experience:</span>
                        <p class="font-medium text-gray-900">${data.experience_years || 'Not specified'}</p>
                    </div>
                </div>
            </div>

            <!-- Analysis Sections -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <!-- Best Match Reason -->
                <div class="bg-white border border-gray-200 rounded-lg p-6">
                    <h4 class="font-semibold text-gray-900 mb-3 flex items-center">
                        <i class="fas fa-star text-yellow-500 mr-2"></i>
                        Why This Candidate Matches
                    </h4>
                    <p class="text-gray-700 leading-relaxed">${data.best_match_reason || 'Strong match based on analysis'}</p>
                </div>

                <!-- Summary -->
                <div class="bg-white border border-gray-200 rounded-lg p-6">
                    <h4 class="font-semibold text-gray-900 mb-3 flex items-center">
                        <i class="fas fa-clipboard-list text-blue-500 mr-2"></i>
                        Summary
                    </h4>
                    <p class="text-gray-700 leading-relaxed">${data.summary || 'Candidate shows good potential for this role'}</p>
                </div>

                <!-- Key Strengths -->
                ${data.key_strengths && data.key_strengths.length > 0 ? `
                <div class="bg-white border border-gray-200 rounded-lg p-6">
                    <h4 class="font-semibold text-gray-900 mb-3 flex items-center">
                        <i class="fas fa-thumbs-up text-green-500 mr-2"></i>
                        Key Strengths
                    </h4>
                    <ul class="space-y-2">
                        ${data.key_strengths.map(strength => `
                            <li class="flex items-start">
                                <div class="w-2 h-2 bg-green-500 rounded-full mt-2 mr-3 flex-shrink-0"></div>
                                <span class="text-gray-700">${strength}</span>
                            </li>
                        `).join('')}
                    </ul>
                </div>
                ` : ''}

                <!-- Missing Elements -->
                ${data.missing_elements && data.missing_elements.length > 0 ? `
                <div class="bg-white border border-gray-200 rounded-lg p-6">
                    <h4 class="font-semibold text-gray-900 mb-3 flex items-center">
                        <i class="fas fa-exclamation-triangle text-yellow-500 mr-2"></i>
                        Areas for Improvement
                    </h4>
                    <ul class="space-y-2">
                        ${data.missing_elements.map(element => `
                            <li class="flex items-start">
                                <div class="w-2 h-2 bg-yellow-500 rounded-full mt-2 mr-3 flex-shrink-0"></div>
                                <span class="text-gray-700">${element}</span>
                            </li>
                        `).join('')}
                    </ul>
                </div>
                ` : ''}
            </div>

            <!-- Skills and Experience -->
            <div class="mt-6 space-y-6">
                <!-- Matching Skills -->
                ${data.matching_skills && data.matching_skills.length > 0 ? `
                <div class="bg-white border border-gray-200 rounded-lg p-6">
                    <h4 class="font-semibold text-gray-900 mb-3 flex items-center">
                        <i class="fas fa-cogs text-blue-500 mr-2"></i>
                        Matching Skills
                    </h4>
                    <div class="flex flex-wrap gap-2">
                        ${data.matching_skills.map(skill => `
                            <span class="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">${skill}</span>
                        `).join('')}
                    </div>
                </div>
                ` : ''}

                <!-- Relevant Experience -->
                ${data.relevant_experience ? `
                <div class="bg-white border border-gray-200 rounded-lg p-6">
                    <h4 class="font-semibold text-gray-900 mb-3 flex items-center">
                        <i class="fas fa-briefcase text-purple-500 mr-2"></i>
                        Relevant Experience
                    </h4>
                    <p class="text-gray-700 leading-relaxed">${data.relevant_experience}</p>
                </div>
                ` : ''}

                <!-- Recommendations -->
                ${data.recommendations && data.recommendations.length > 0 ? `
                <div class="bg-white border border-gray-200 rounded-lg p-6">
                    <h4 class="font-semibold text-gray-900 mb-3 flex items-center">
                        <i class="fas fa-lightbulb text-orange-500 mr-2"></i>
                        Recommendations
                    </h4>
                    <ul class="space-y-2">
                        ${data.recommendations.map(rec => `
                            <li class="flex items-start">
                                <div class="w-2 h-2 bg-orange-500 rounded-full mt-2 mr-3 flex-shrink-0"></div>
                                <span class="text-gray-700">${rec}</span>
                            </li>
                        `).join('')}
                    </ul>
                </div>
                ` : ''}
            </div>
        `;
    }

    // Function to generate comprehensive HR scorecard content
    function generateHRScorecardContent(analysisData) {
        const scorecard = analysisData.hr_scorecard;
        const overview = scorecard.candidate_overview || {};
        const breakdown = scorecard.score_breakdown || {};
        const keywords = scorecard.keyword_coverage || {};
        const timeline = scorecard.career_timeline || [];
        const recommendations = scorecard.recommendations || {};
        const detailed = scorecard.detailed_analysis || {};

        // Determine match status color
        const getMatchStatusColor = (status) => {
            switch (status) {
                case 'Strong Fit': return 'bg-green-100 text-green-800 border-green-200';
                case 'Medium Fit': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
                case 'Weak Fit': return 'bg-red-100 text-red-800 border-red-200';
                default: return 'bg-gray-100 text-gray-800 border-gray-200';
            }
        };

        const getScoreColor = (score) => {
            if (score >= 80) return 'text-green-600';
            if (score >= 60) return 'text-yellow-600';
            return 'text-red-600';
        };

        return `
            <div class="hr-scorecard space-y-6">
                <!-- Candidate Overview -->
                <div class="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-6 border border-blue-200">
                    <div class="flex items-start justify-between mb-4">
                        <div class="flex-1">
                            <div class="flex items-center gap-3 mb-2">
                                <h3 class="text-xl font-bold text-gray-900">${overview.name || 'Unknown Candidate'}</h3>
                                <span class="px-3 py-1 rounded-full text-sm font-medium border ${getMatchStatusColor(overview.match_status)}">
                                    ${overview.match_status || 'Unknown Fit'}
                                </span>
                            </div>
                            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                                <div>
                                    <span class="text-gray-500">Position:</span>
                                    <div class="font-medium">${overview.position_applied_for || 'Not specified'}</div>
                                </div>
                                <div>
                                    <span class="text-gray-500">Experience:</span>
                                    <div class="font-medium">${overview.experience_years || 'Not specified'}</div>
                                </div>
                                <div>
                                    <span class="text-gray-500">Location:</span>
                                    <div class="font-medium">${overview.location || 'Not specified'}</div>
                                </div>
                                <div>
                                    <span class="text-gray-500">Contact:</span>
                                    <div class="font-medium">
                                        ${overview.email ? `<div>${overview.email}</div>` : ''}
                                        ${overview.phone ? `<div>${overview.phone}</div>` : ''}
                                        ${!overview.email && !overview.phone ? 'Not available' : ''}
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="text-center ml-6">
                            <div class="text-4xl font-bold ${getScoreColor(overview.overall_match_score || 0)}">
                                ${overview.overall_match_score || 0}%
                            </div>
                            <div class="text-gray-600 text-sm font-medium">Overall Match</div>
                        </div>
                    </div>
                </div>

                <!-- Score Breakdown -->
                <div class="bg-white rounded-xl p-6 border border-gray-200">
                    <h4 class="text-lg font-semibold text-gray-900 mb-4">📊 Score Breakdown</h4>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        ${Object.entries(breakdown).filter(([category, data]) => {
            // Hide specific sections from HR scorecard display
            const hiddenSections = [
                'experience_level_fit',
                'keyword_technical_match',
                'final_scoring_summary'
            ];
            return !hiddenSections.includes(category.toLowerCase());
        }).map(([category, data]) => `
                            <div class="bg-gray-50 rounded-lg p-4">
                                <div class="flex items-center justify-between mb-2">
                                    <span class="font-medium text-gray-900 capitalize">${category.replace('_', ' ')}</span>
                                    <span class="text-lg font-bold ${getScoreColor(data.score || 0)}">${data.score || 0}%</span>
                                </div>
                                <p class="text-sm text-gray-600">${data.comment || 'No comment available'}</p>
                            </div>
                        `).join('')}
                    </div>
                </div>

                <!-- Keyword Coverage -->
                <div class="bg-white rounded-xl p-6 border border-gray-200">
                    <h4 class="text-lg font-semibold text-gray-900 mb-4">🔑 Keyword Coverage</h4>
                    <div class="mb-4">
                        <div class="flex items-center justify-between mb-2">
                            <span class="text-gray-700">Keywords Matched</span>
                            <span class="font-bold">${keywords.jd_keywords_matched || 0} / ${keywords.total_jd_keywords || 0}</span>
                        </div>
                        <div class="w-full bg-gray-200 rounded-full h-2">
                            <div class="bg-blue-600 h-2 rounded-full" style="width: ${keywords.total_jd_keywords ? (keywords.jd_keywords_matched / keywords.total_jd_keywords * 100) : 0}%"></div>
                        </div>
                    </div>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <h5 class="font-medium text-green-700 mb-2">? Matched Keywords</h5>
                            <div class="flex flex-wrap gap-1">
                                ${(keywords.matched_keywords || []).map(keyword =>
            `<span class="px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs">${keyword}</span>`
        ).join('')}
                            </div>
                        </div>
                        <div>
                            <h5 class="font-medium text-red-700 mb-2">? Missing Keywords</h5>
                            <div class="flex flex-wrap gap-1">
                                ${(keywords.missing_keywords || []).map(keyword =>
            `<span class="px-2 py-1 bg-red-100 text-red-800 rounded-full text-xs">${keyword}</span>`
        ).join('')}
                            </div>
                        </div>
                    </div>
                </div>

                                    <!-- Analysis Summary -->
                    <div class="bg-white rounded-xl p-6 border border-gray-200">
                        <h4 class="text-lg font-semibold text-gray-900 mb-6">📋 Analysis Summary</h4>
                        
                        <!-- AI Analysis -->
                        <div class="mb-6">
                            <h5 class="text-md font-medium text-gray-800 mb-3">🤖 AI Analysis</h5>
                            <p class="text-gray-700 leading-relaxed">
                                ${scorecard.analysis_summary ? scorecard.analysis_summary.ai_analysis :
                (scorecard.ai_summary || 'No analysis available')}
                            </p>
                        </div>

                        <!-- Resume Highlights -->
                        ${(scorecard.analysis_summary && scorecard.analysis_summary.resume_highlights && scorecard.analysis_summary.resume_highlights.length > 0) ||
                (scorecard.resume_snippets && scorecard.resume_snippets.length > 0) ? `
                            <div class="mb-6">
                                <h5 class="text-md font-medium text-gray-800 mb-3">⭐ Resume Highlights</h5>
                                <div class="space-y-3">
                                    ${((scorecard.analysis_summary && scorecard.analysis_summary.resume_highlights) || scorecard.resume_snippets || []).map(highlight => `
                                        <div class="bg-blue-50 border-l-4 border-blue-400 p-4 rounded-r-lg relative">
                                            <div class="quote-circle-small">
                                                <i class="fas fa-quote-left"></i>
                                            </div>
                                            <p class="text-blue-900 text-sm pl-8">${highlight}</p>
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                        ` : ''}

                        <!-- HR Recommendations -->
                        <div>
                            <h5 class="text-md font-medium text-gray-800 mb-3">💼 HR Recommendations</h5>
                            <div class="space-y-3">
                                ${(() => {
                const rec = scorecard.analysis_summary ? scorecard.analysis_summary.hr_recommendations : recommendations;
                return `
                                        <div class="flex items-center justify-between p-3 bg-green-50 rounded-lg">
                                            <span class="font-medium text-green-800">
                                                ${rec && rec.action === 'Shortlist' ? '?' : '?'} ${rec ? rec.action : 'No action specified'}
                                            </span>
                                            <span class="text-sm text-green-600">${rec ? rec.priority : 'Normal'} Priority</span>
                                        </div>
                                        

                                    `;
            })()}
                            </div>
                        </div>
                    </div>

                <!-- Career Timeline -->
                ${timeline.length > 0 ? `
                    <div class="bg-white rounded-xl p-6 border border-gray-200">
                        <h4 class="text-lg font-semibold text-gray-900 mb-4">📈 Career Timeline</h4>
                        <div class="space-y-4">
                            ${timeline.map(job => `
                                <div class="flex items-start space-x-4 p-4 bg-gray-50 rounded-lg">
                                    <div class="text-sm font-medium text-gray-600 min-w-0 flex-shrink-0">
                                        ${job.year_range}
                                    </div>
                                    <div class="flex-1 min-w-0">
                                        <h5 class="font-medium text-gray-900">${job.role}</h5>
                                        <p class="text-gray-600 text-sm">${job.company}</p>
                                        <div class="flex flex-wrap gap-1 mt-2">
                                            ${(job.key_skills || []).map(skill =>
                `<span class="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs">${skill}</span>`
            ).join('')}
                                        </div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}

                <!-- Benchmark & Recommendations -->
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="bg-white rounded-xl p-6 border border-gray-200">
                        <h4 class="text-lg font-semibold text-gray-900 mb-4">🎯 Benchmark Position</h4>
                        <div class="text-center">
                            <div class="text-2xl font-bold text-blue-600 mb-2">
                                ${scorecard.benchmark_position || 'Not calculated'}
                            </div>
                            <p class="text-gray-600 text-sm">Among all applicants screened</p>
                        </div>
                    </div>

                    <div class="bg-white rounded-xl p-6 border border-gray-200">
                        <h4 class="text-lg font-semibold text-gray-900 mb-4">? Quick Actions</h4>
                        <div class="space-y-3">
                            <div class="text-center">
                                <div class="text-2xl font-bold text-green-600 mb-2">
                                    ${scorecard.quick_action ? scorecard.quick_action.recommended_action :
                (scorecard.recommendations && scorecard.recommendations.action ? scorecard.recommendations.action : 'Review Required')}
                                </div>
                                <p class="text-gray-600 text-sm">Recommended Action</p>
                                ${scorecard.quick_action && scorecard.quick_action.confidence_level ? `
                                    <div class="mt-2">
                                        <span class="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs">
                                            ${scorecard.quick_action.confidence_level} Confidence
                                        </span>
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Additional Details -->
                ${Object.keys(detailed).length > 0 ? `
                    <div class="bg-white rounded-xl p-6 border border-gray-200">
                        <h4 class="text-lg font-semibold text-gray-900 mb-4">📝 Additional Details</h4>
                        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
                            ${Object.entries(detailed).map(([key, value]) => `
                                <div>
                                    <span class="text-gray-500 capitalize">${key.replace('_', ' ')}:</span>
                                    <div class="font-medium">
                                        ${Array.isArray(value) ? value.join(', ') : value || 'Not specified'}
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
    }

    // ------------------------------------------------------------------
    // Re-export closure-scoped helpers to `window` so dynamically-rendered
    // onclick="-" attributes can reach them. Functions defined directly
    // inside this DOMContentLoaded callback are NOT global by default.
    // Add new entries here whenever you add a function that an inline
    // onclick attribute references.
    // ------------------------------------------------------------------
    try {
        const _exports = {
            showLoadingMessage: typeof showLoadingMessage !== 'undefined' ? showLoadingMessage : null,
            hideLoadingMessage: typeof hideLoadingMessage !== 'undefined' ? hideLoadingMessage : null,
            updateSearchProgress: typeof updateSearchProgress !== 'undefined' ? updateSearchProgress : null,
            generateEnhancedResults: typeof generateEnhancedResults !== 'undefined' ? generateEnhancedResults : null,
            pollHRScorecardTask: typeof pollHRScorecardTask !== 'undefined' ? pollHRScorecardTask : null,
            exportCandidateReport: typeof exportCandidateReport !== 'undefined' ? exportCandidateReport : null,
            exportAllCandidatesReport: typeof exportAllCandidatesReport !== 'undefined' ? exportAllCandidatesReport : null,
            setCandidateStatus: typeof setCandidateStatus !== 'undefined' ? setCandidateStatus : null,
            removeFile: typeof removeFile !== 'undefined' ? removeFile : null,
            removeSkill: typeof removeSkill !== 'undefined' ? removeSkill : null,
            closeAnalysisModal: typeof closeAnalysisModal !== 'undefined' ? closeAnalysisModal : null,
            loadSavedSearch: typeof loadSavedSearch !== 'undefined' ? loadSavedSearch : null,
            loadPage: typeof loadPage !== 'undefined' ? loadPage : null,
            showNotification: typeof showNotification !== 'undefined' ? showNotification : null,
            loadCandidateStatusCounts: typeof loadCandidateStatusCounts !== 'undefined' ? loadCandidateStatusCounts : null,
            loadUpcomingEvents: typeof loadUpcomingEvents !== 'undefined' ? loadUpcomingEvents : null,
        };
        Object.keys(_exports).forEach(function (k) {
            if (typeof _exports[k] === 'function' && typeof window[k] !== 'function') {
                window[k] = _exports[k];
            }
        });
    } catch (e) { console.warn('Handler re-export failed:', e); }

    // Set active navigation link
    setActiveLink(dashboardLink);
    loadPage('dashboard');
});

// Helper function to download resume
function downloadResume(filePath) {
    if (filePath) {
        // Create a temporary link to download the file
        const link = document.createElement('a');
        link.href = `/api/download-resume?file_path=${encodeURIComponent(filePath)}`;
        link.download = filePath.split('/').pop(); // Get filename from path
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    } else {
        alert('Resume file not available for download');
    }
}

// =============================================================================
// PDF EXPORT - Improved candidate / bulk reports (jsPDF + autotable)
// =============================================================================

// Lazy-load jsPDF + jspdf-autotable. Returns a Promise resolved when both are
// available on `window.jspdf` (UMD). Cached after first load.
let _pdfLibsPromise = null;
function ensurePdfLibsLoaded() {
    if (window.jspdf && window.jspdf.jsPDF && window.jspdf.autoTable) {
        return Promise.resolve();
    }
    if (_pdfLibsPromise) return _pdfLibsPromise;

    function loadScript(src) {
        return new Promise(function (resolve, reject) {
            const s = document.createElement('script');
            s.src = src;
            s.onload = resolve;
            s.onerror = function () { reject(new Error('Failed to load ' + src)); };
            document.head.appendChild(s);
        });
    }

    _pdfLibsPromise = (window.jspdf && window.jspdf.jsPDF
        ? Promise.resolve()
        : loadScript('https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js'))
        .then(function () {
            return loadScript('https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.8.2/jspdf.plugin.autotable.min.js');
        })
        .then(function () {
            if (window.PDFLib && window.PDFLib.PDFDocument) return;
            return loadScript('https://cdnjs.cloudflare.com/ajax/libs/pdf-lib/1.17.1/pdf-lib.min.js')
                .catch(function (e) {
                    // pdf-lib is only required for merging attached resumes; report builds without it.
                    console.warn('pdf-lib failed to load; resume attachments will be skipped.', e);
                });
        });
    return _pdfLibsPromise;
}

// Color band for a numeric score (0-100). Returns RGB array.
// Matches HR scorecard UI thresholds (getScoreColor in dashboard): 80 / 60.
function _scoreColor(score) {
    const s = Number(score) || 0;
    if (s >= 80) return [22, 163, 74];   // green-600  (Strong Fit)
    if (s >= 60) return [202, 138, 4];   // yellow-600 (Medium Fit)
    return [220, 38, 38];                // red-600    (Weak Fit)
}

function _safe(val, fallback) {
    if (val === null || val === undefined || val === '') return fallback || 'Not specified';
    return String(val);
}

function _humanize(key) {
    return String(key || '').replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
}

// Brand palette (matches the site: primary blue #3B82F6 / blue-700 / emerald accent).
// Kept as a single source of truth so the report stays on-brand.
const _BRAND = {
    blue50:  [239, 246, 255],
    blue100: [219, 234, 254],
    blue200: [191, 219, 254],
    blue400: [96, 165, 250],
    blue500: [59, 130, 246],   // primary
    blue600: [37, 99, 235],
    blue700: [29, 78, 216],
    blue800: [30, 64, 175],    // primary-dark
    blue900: [30, 58, 138],
    slate50: [248, 250, 252],
    slate100: [241, 245, 249],
    slate200: [226, 232, 240],
    slate500: [100, 116, 139],
    slate600: [71, 85, 105],
    slate700: [51, 65, 85],
    slate800: [30, 41, 59],
    slate900: [15, 23, 42],
    emerald50:  [236, 253, 245],
    emerald600: [5, 150, 105],
    emerald700: [4, 120, 87],
    amber50:    [255, 251, 235],
    amber600:   [217, 119, 6],
    rose50:     [255, 241, 242],
    rose600:    [225, 29, 72],
    rose700:    [190, 18, 60],
};

function _setFill(doc, rgb)  { doc.setFillColor(rgb[0], rgb[1], rgb[2]); }
function _setText(doc, rgb)  { doc.setTextColor(rgb[0], rgb[1], rgb[2]); }
function _setDraw(doc, rgb)  { doc.setDrawColor(rgb[0], rgb[1], rgb[2]); }

// Draw a section header bar: soft blue fill + accent stripe + numbered title.
// Returns new y position (below the underline).
function _drawSectionHeader(doc, num, title, y, pageWidth, margin) {
    const barH = 8;
    // Soft blue-50 background bar
    _setFill(doc, _BRAND.blue50);
    doc.rect(margin, y, pageWidth - 2 * margin, barH, 'F');
    // Left accent block (blue-600)
    _setFill(doc, _BRAND.blue600);
    doc.rect(margin, y, 2, barH, 'F');
    // Title text
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(10.8);
    _setText(doc, _BRAND.blue800);
    doc.text(String(num).padStart(2, '0') + '   ' + title, margin + 5, y + 5.6);
    return y + barH + 4;
}

// Render a single candidate's report into an existing jsPDF doc.
// Adds a new page first if `addPage` is true.
// opts.jobTitle is used as a fallback when the candidate analysis itself
// doesn't carry a position_applied_for value.
function _renderCandidateSection(doc, analysisData, candidateName, opts) {
    opts = opts || {};
    const pageWidth = doc.internal.pageSize.getWidth();
    const pageHeight = doc.internal.pageSize.getHeight();
    const margin = 14;
    const contentWidth = pageWidth - 2 * margin;
    const overview = analysisData.candidate_overview || {};
    const score = Number(overview.overall_match_score || analysisData.match_score || 0);
    const status = _safe(overview.match_status, 'Unreviewed');
    const recommendation = _safe(analysisData.recommendation || overview.recommendation, '');
    const positionLabel = String(overview.position_applied_for || opts.jobTitle || '').trim();

    if (opts.addPage) doc.addPage();

    // Helper: ensure at least `need` mm of vertical space; new page if not.
    const ensureSpace = function (cy, need) {
        if (cy + need > pageHeight - 14) { doc.addPage(); return 20; }
        return cy;
    };

    // ---- Header banner (brand blue) -------------------------------------
    _setFill(doc, _BRAND.blue700);
    doc.rect(0, 0, pageWidth, 40, 'F');
    _setFill(doc, _BRAND.blue400);   // accent stripe
    doc.rect(0, 40, pageWidth, 1.6, 'F');
    doc.setTextColor(255, 255, 255);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(8.5);
    _setText(doc, _BRAND.blue200);
    doc.text('SMART HR  \u2022  CANDIDATE ANALYSIS', margin, 10);
    doc.setTextColor(255, 255, 255);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(16);
    doc.text(_safe(overview.name || candidateName), margin, 20);
    if (positionLabel) {
        doc.setFont('helvetica', 'normal');
        doc.setFontSize(10);
        _setText(doc, _BRAND.blue100);
        doc.text(positionLabel, margin, 28);
    }
    // Compact meta row (experience / location) under the position
    const meta = [];
    if (overview.experience_years) meta.push(String(overview.experience_years));
    if (overview.location) meta.push(String(overview.location));
    if (meta.length) {
        doc.setFont('helvetica', 'normal');
        doc.setFontSize(8.5);
        _setText(doc, _BRAND.blue200);
        doc.text(meta.join('   \u2022   '), margin, positionLabel ? 34 : 28);
    }
    // Score badge (top right)
    const badgeColor = _scoreColor(score);
    doc.setFillColor.apply(doc, badgeColor);
    doc.roundedRect(pageWidth - margin - 38, 9, 38, 24, 3.5, 3.5, 'F');
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(17);
    doc.setTextColor(255, 255, 255);
    doc.text(score + '%', pageWidth - margin - 19, 21, { align: 'center' });
    doc.setFontSize(7);
    doc.setFont('helvetica', 'bold');
    doc.text(status.toUpperCase(), pageWidth - margin - 19, 28, { align: 'center' });

    let y = 50;
    let sec = 1;
    _setText(doc, _BRAND.slate900);

    // ---- 1. Candidate snapshot (boxed grid) -----------------------------
    y = _drawSectionHeader(doc, sec++, 'Candidate Snapshot', y, pageWidth, margin);
    doc.autoTable({
        startY: y,
        margin: { left: margin, right: margin },
        theme: 'grid',
        styles: { fontSize: 9, cellPadding: 2.4, lineColor: _BRAND.slate200, lineWidth: 0.15, textColor: _BRAND.slate800 },
        columnStyles: {
            0: { fontStyle: 'bold', cellWidth: 32, textColor: _BRAND.slate600, fillColor: _BRAND.slate50 },
            1: { cellWidth: contentWidth / 2 - 32 },
            2: { fontStyle: 'bold', cellWidth: 32, textColor: _BRAND.slate600, fillColor: _BRAND.slate50 },
            3: { cellWidth: contentWidth / 2 - 32 },
        },
        body: [
            ['Email', _safe(overview.email, '-'), 'Phone', _safe(overview.phone, '-')],
            ['Location', _safe(overview.location, '-'), 'Experience', _safe(overview.experience_years, '-')],
            ['Position', positionLabel || '-', 'Match Status', status],
            ['Score', score + '%', 'Recommendation', recommendation || '-'],
        ],
    });
    y = doc.lastAutoTable.finalY + 7;

    // ---- 2. AI summary (callout box) ------------------------------------
    if (analysisData.ai_summary) {
        const text = String(analysisData.ai_summary);
        const wrapWidth = contentWidth - 10;
        const lines = doc.splitTextToSize(text, wrapWidth);
        const boxH = lines.length * 4.5 + 7;
        y = ensureSpace(y, 12 + boxH);
        y = _drawSectionHeader(doc, sec++, 'AI Summary', y, pageWidth, margin);
        // Soft callout: blue-50 fill, blue-400 left border
        _setFill(doc, _BRAND.blue50);
        doc.rect(margin, y, contentWidth, boxH, 'F');
        _setFill(doc, _BRAND.blue400);
        doc.rect(margin, y, 1.8, boxH, 'F');
        doc.setFont('helvetica', 'normal');
        doc.setFontSize(9);
        _setText(doc, _BRAND.slate800);
        let ty = y + 5.5;
        lines.forEach(function (ln) {
            if (ty > pageHeight - 14) { doc.addPage(); ty = 20; }
            doc.text(ln, margin + 5, ty);
            ty += 4.5;
        });
        y = y + boxH + 7;
    }

    // ---- 3. Score breakdown table ---------------------------------------
    if (analysisData.score_breakdown && typeof analysisData.score_breakdown === 'object') {
        const rows = Object.entries(analysisData.score_breakdown)
            .filter(function (kv) { return kv[1] && typeof kv[1] === 'object' && 'score' in kv[1]; })
            .map(function (kv) {
                const sc = Number(kv[1].score) || 0;
                return [_humanize(kv[0]), sc + '%', _safe(kv[1].comment, '-')];
            });
        if (rows.length) {
            y = ensureSpace(y, 30);
            y = _drawSectionHeader(doc, sec++, 'Score Breakdown', y, pageWidth, margin);
            doc.autoTable({
                startY: y,
                margin: { left: margin, right: margin },
                head: [['Category', 'Score', 'Assessment']],
                body: rows,
                styles: { fontSize: 8.7, cellPadding: 2.3, overflow: 'linebreak', lineColor: _BRAND.slate200, lineWidth: 0.15, textColor: _BRAND.slate800 },
                headStyles: { fillColor: _BRAND.blue600, textColor: [255, 255, 255], fontStyle: 'bold', halign: 'left' },
                alternateRowStyles: { fillColor: _BRAND.slate50 },
                columnStyles: {
                    0: { cellWidth: 52, fontStyle: 'bold' },
                    1: { cellWidth: 20, halign: 'center', fontStyle: 'bold' },
                    2: { cellWidth: contentWidth - 72 },
                },
                didParseCell: function (data) {
                    if (data.section === 'body' && data.column.index === 1) {
                        const sc = parseInt(data.cell.raw, 10);
                        if (!isNaN(sc)) {
                            const c = _scoreColor(sc);
                            data.cell.styles.fillColor = c;
                            data.cell.styles.textColor = [255, 255, 255];
                        }
                    }
                },
            });
            y = doc.lastAutoTable.finalY + 6;
        }
    }

    // ---- 4. Strengths vs Concerns (parallel) ----------------------------
    const strengths = (analysisData.key_strengths || analysisData.strengths || []).filter(Boolean);
    const concerns = (analysisData.potential_concerns || analysisData.concerns || analysisData.red_flags || []).filter(Boolean);
    if (strengths.length || concerns.length) {
        y = ensureSpace(y, 30);
        y = _drawSectionHeader(doc, sec++, 'Strengths & Concerns', y, pageWidth, margin);
        const maxRows = Math.max(strengths.length, concerns.length);
        const body = [];
        for (let i = 0; i < maxRows; i++) {
            body.push([
                strengths[i] ? String(strengths[i]) : '',
                concerns[i] ? String(concerns[i]) : '',
            ]);
        }
        doc.autoTable({
            startY: y,
            margin: { left: margin, right: margin },
            head: [['Key Strengths (' + strengths.length + ')', 'Potential Concerns (' + concerns.length + ')']],
            body: body,
            styles: { fontSize: 8.7, cellPadding: 2.6, overflow: 'linebreak', lineColor: _BRAND.slate200, lineWidth: 0.15 },
            headStyles: {
                fillColor: _BRAND.slate100, textColor: _BRAND.slate700, fontStyle: 'bold',
            },
            columnStyles: {
                0: { cellWidth: contentWidth / 2, textColor: _BRAND.emerald700, fillColor: _BRAND.emerald50 },
                1: { cellWidth: contentWidth / 2, textColor: _BRAND.rose700, fillColor: _BRAND.rose50 },
            },
        });
        y = doc.lastAutoTable.finalY + 7;
    }

    // ---- 5. Keyword coverage --------------------------------------------
    if (analysisData.keyword_coverage) {
        const kc = analysisData.keyword_coverage;
        const matched = (kc.matched_keywords || []).filter(Boolean);
        const missing = (kc.missing_keywords || []).filter(Boolean);
        if (matched.length || missing.length) {
            y = ensureSpace(y, 30);
            y = _drawSectionHeader(doc, sec++, 'Keyword Coverage', y, pageWidth, margin);
            const totalK = matched.length + missing.length;
            const pct = totalK ? Math.round((matched.length / totalK) * 100) : 0;
            // Progress bar
            const barW = contentWidth;
            const barY = y;
            _setFill(doc, _BRAND.slate200);
            doc.roundedRect(margin, barY, barW, 3.5, 1.5, 1.5, 'F');
            _setFill(doc, _BRAND.emerald600);
            const fillW = Math.max(0, (barW * pct) / 100);
            if (fillW > 0) doc.roundedRect(margin, barY, fillW, 3.5, 1.5, 1.5, 'F');
            doc.setFont('helvetica', 'normal');
            doc.setFontSize(8.5);
            _setText(doc, _BRAND.slate600);
            doc.text(matched.length + ' / ' + totalK + ' matched  (' + pct + '%)', margin, barY + 9);
            y = barY + 12;
            doc.autoTable({
                startY: y,
                margin: { left: margin, right: margin },
                head: [['Matched Keywords (' + matched.length + ')', 'Missing Keywords (' + missing.length + ')']],
                body: [[matched.join(', ') || '-', missing.join(', ') || '-']],
                styles: { fontSize: 8.7, cellPadding: 2.6, overflow: 'linebreak', lineColor: _BRAND.slate200, lineWidth: 0.15 },
                headStyles: { fillColor: _BRAND.slate100, textColor: _BRAND.slate700, fontStyle: 'bold' },
                columnStyles: {
                    0: { cellWidth: contentWidth / 2, textColor: _BRAND.emerald700, fillColor: _BRAND.emerald50 },
                    1: { cellWidth: contentWidth / 2, textColor: _BRAND.rose700, fillColor: _BRAND.rose50 },
                },
            });
            y = doc.lastAutoTable.finalY + 7;
        }
    }

    // ---- 6. Career timeline ---------------------------------------------
    if (Array.isArray(analysisData.career_timeline) && analysisData.career_timeline.length) {
        y = ensureSpace(y, 30);
        y = _drawSectionHeader(doc, sec++, 'Career Timeline', y, pageWidth, margin);
        const rows = analysisData.career_timeline.slice(0, 12).map(function (item) {
            return [
                _safe(item.year_range || item.period, '-'),
                _safe(item.role, '-'),
                _safe(item.company, '-'),
                Array.isArray(item.key_skills) ? item.key_skills.slice(0, 6).join(', ') : '',
            ];
        });
        doc.autoTable({
            startY: y,
            margin: { left: margin, right: margin },
            head: [['Period', 'Role', 'Company', 'Key Skills']],
            body: rows,
            styles: { fontSize: 8.6, cellPadding: 2.2, overflow: 'linebreak', lineColor: _BRAND.slate200, lineWidth: 0.15, textColor: _BRAND.slate800 },
            headStyles: { fillColor: _BRAND.blue600, textColor: [255, 255, 255], fontStyle: 'bold' },
            alternateRowStyles: { fillColor: _BRAND.slate50 },
            columnStyles: {
                0: { cellWidth: 26 },
                1: { cellWidth: 44, fontStyle: 'bold' },
                2: { cellWidth: 44 },
                3: { cellWidth: contentWidth - 114 },
            },
        });
        y = doc.lastAutoTable.finalY + 7;
    }

    // ---- 7. Tenure prediction -------------------------------------------
    if (analysisData.tenure_prediction) {
        const tp = analysisData.tenure_prediction;
        y = ensureSpace(y, 30);
        y = _drawSectionHeader(doc, sec++, 'Tenure Prediction', y, pageWidth, margin);
        doc.autoTable({
            startY: y,
            margin: { left: margin, right: margin },
            theme: 'grid',
            styles: { fontSize: 9, cellPadding: 2.2, lineColor: _BRAND.slate200, lineWidth: 0.15, textColor: _BRAND.slate800 },
            columnStyles: {
                0: { fontStyle: 'bold', cellWidth: 50, textColor: _BRAND.slate600, fillColor: _BRAND.slate50 },
                1: { cellWidth: contentWidth - 50 },
            },
            body: [
                ['Estimated Tenure', _safe(tp.estimated_tenure, '-')],
                ['Retention Score', _safe(tp.tenure_score, '-') + (tp.tenure_score ? '%' : '')],
                ['Confidence', _safe(tp.confidence_level, '-')],
            ],
        });
        y = doc.lastAutoTable.finalY + 5;

        if (tp.factors && typeof tp.factors === 'object') {
            const fRows = Object.entries(tp.factors)
                .filter(function (kv) { return kv[1] && typeof kv[1] === 'object'; })
                .map(function (kv) { return [_humanize(kv[0]), (kv[1].score || 0) + '%', _safe(kv[1].analysis, '-')]; });
            if (fRows.length) {
                y = ensureSpace(y, 24);
                doc.autoTable({
                    startY: y,
                    margin: { left: margin, right: margin },
                    head: [['Tenure Factor', 'Score', 'Analysis']],
                    body: fRows,
                    styles: { fontSize: 8.6, cellPadding: 2.2, overflow: 'linebreak', lineColor: _BRAND.slate200, lineWidth: 0.15, textColor: _BRAND.slate800 },
                    headStyles: { fillColor: _BRAND.blue600, textColor: [255, 255, 255], fontStyle: 'bold' },
                    alternateRowStyles: { fillColor: _BRAND.slate50 },
                    columnStyles: { 0: { cellWidth: 52, fontStyle: 'bold' }, 1: { cellWidth: 20, halign: 'center', fontStyle: 'bold' }, 2: { cellWidth: contentWidth - 72 } },
                    didParseCell: function (data) {
                        if (data.section === 'body' && data.column.index === 1) {
                            const sc = parseInt(data.cell.raw, 10);
                            if (!isNaN(sc)) {
                                const c = _scoreColor(sc);
                                data.cell.styles.fillColor = c;
                                data.cell.styles.textColor = [255, 255, 255];
                            }
                        }
                    },
                });
                y = doc.lastAutoTable.finalY + 4;
            }
        }
    }
}

// Add running footer to every page (page X of Y, generation timestamp).
function _addPdfFooter(doc, label) {
    const pageCount = doc.internal.getNumberOfPages();
    const w = doc.internal.pageSize.getWidth();
    const h = doc.internal.pageSize.getHeight();
    const stamp = new Date().toLocaleString();
    for (let i = 1; i <= pageCount; i++) {
        doc.setPage(i);
        // Thin separator line above footer
        _setDraw(doc, _BRAND.slate200);
        doc.setLineWidth(0.2);
        doc.line(14, h - 10, w - 14, h - 10);
        doc.setFont('helvetica', 'normal');
        doc.setFontSize(7.5);
        _setText(doc, _BRAND.slate500);
        doc.text(label || 'Smart HR - AI Recruitment Report', 14, h - 6);
        doc.text(stamp + '   |   Page ' + i + ' of ' + pageCount, w - 14, h - 6, { align: 'right' });
    }
}

// Export a single candidate's report (uses the shared _renderCandidateSection
// renderer so single-export and bulk-export look identical).
function exportCandidateReport(candidateName, candidateIndex, filePath) {
    try {
        const card = document.querySelector('.professional-resume-card[data-candidate-index="' + candidateIndex + '"]');
        if (!card) {
            showNotification('Error: Could not find candidate data for export', 'error');
            return;
        }
        const analysisDataString = card.getAttribute('data-analysis-data');
        if (!analysisDataString) {
            showNotification('Error: No analysis data available for export', 'error');
            return;
        }
        let analysisData;
        try {
            analysisData = JSON.parse(analysisDataString);
        } catch (parseError) {
            showNotification('Error: Invalid analysis data format', 'error');
            return;
        }

        showNotification('Generating PDF report-', 'info');
        ensurePdfLibsLoaded()
            .then(function () {
                const { jsPDF } = window.jspdf;
                const doc = new jsPDF({ unit: 'mm', format: 'a4' });
                doc.setProperties({
                    title: 'Smart HR - Candidate Report - ' + candidateName,
                    author: 'Smart HR',
                    subject: 'Candidate Analysis Report',
                    creator: 'Smart HR',
                });
                _renderCandidateSection(doc, analysisData, candidateName, {
                    addPage: false,
                    jobTitle: (window.searchResultsData && (window.searchResultsData.job_title || window.searchResultsData.position)) || ''
                });
                _addPdfFooter(doc, 'Smart HR - Candidate Report');
                const fileName = 'HR_Report_' + candidateName.replace(/[^a-zA-Z0-9]/g, '_') + '_' + new Date().toISOString().split('T')[0] + '.pdf';
                doc.save(fileName);
                showNotification('Report exported as ' + fileName, 'success');
            })
            .catch(function (err) {
                console.error('PDF export failed:', err);
                showNotification('Could not generate PDF: ' + (err && err.message ? err.message : 'unknown error'), 'error');
            });
    } catch (error) {
        console.error('Error generating PDF report:', error);
        showNotification('Error generating PDF report. Please try again.', 'error');
    }
}

// (Legacy single-candidate ad-hoc PDF renderer removed in 2026-05 cleanup;
//  exportCandidateReport above now delegates to _renderCandidateSection.)


// Helper function to show analysis modal

// Bulk export: one PDF containing a cover summary + per-candidate sections for
// the current search results.
function exportAllCandidatesReport() {
    const data = window.searchResultsData;
    if (!data || !Array.isArray(data.results) || data.results.length === 0) {
        showNotification('No results to export.', 'warning');
        return;
    }
    const candidates = data.results
        .filter(function (r) { return r && r.gemini_analysis; })
        .map(function (r) {
            const a = r.gemini_analysis;
            const ad = a.hr_scorecard || a.analysis_json || {};
            const overview = ad.candidate_overview || {};
            const name = overview.name || r.document_name || 'Unknown Candidate';
            const score = Number(overview.overall_match_score || a.match_score || 0);
            return { name: name, score: score, analysisData: ad, filePath: r.file_path };
        })
        .sort(function (a, b) { return b.score - a.score; });

    if (candidates.length === 0) {
        showNotification('No analyzed candidates available to export.', 'warning');
        return;
    }

    showNotification('Generating bulk PDF report (' + candidates.length + ' candidates)-', 'info');
    ensurePdfLibsLoaded()
        .then(function () {
            const { jsPDF } = window.jspdf;
            const doc = new jsPDF({ unit: 'mm', format: 'a4' });
            const pageWidth = doc.internal.pageSize.getWidth();
            const pageHeight = doc.internal.pageSize.getHeight();
            const margin = 14;
            const contentWidth = pageWidth - 2 * margin;

            // Smart job-title fallback so the cover/sections never look empty
            // at the top even when the search payload omits job_title.
            const jobTitle = (function () {
                const raw = data.job_title || data.position || data.role || '';
                if (raw && String(raw).trim()) return String(raw).trim();
                if (data.query) {
                    const firstLine = String(data.query).split(/[\r\n]/)[0].trim();
                    if (firstLine) return firstLine.length > 70 ? firstLine.slice(0, 67) + '...' : firstLine;
                }
                return 'Candidate Shortlist';
            })();

            doc.setProperties({
                title: 'HR Search Report - ' + jobTitle,
                author: 'Smart HR',
                subject: 'Candidate shortlist',
                creator: 'Smart HR',
            });

            // -- Cover page (brand blue) -----------------------------------
            _setFill(doc, _BRAND.blue700);
            doc.rect(0, 0, pageWidth, 68, 'F');
            _setFill(doc, _BRAND.blue400);    // accent stripe
            doc.rect(0, 68, pageWidth, 1.8, 'F');
            _setText(doc, _BRAND.blue200);
            doc.setFont('helvetica', 'bold');
            doc.setFontSize(9.5);
            doc.text('SMART HR  \u2022  AI RECRUITMENT', margin, 14);
            doc.setTextColor(255, 255, 255);
            doc.setFont('helvetica', 'bold');
            doc.setFontSize(24);
            doc.text('Candidate Shortlist Report', margin, 32);
            doc.setFont('helvetica', 'bold');
            doc.setFontSize(13);
            _setText(doc, _BRAND.blue100);
            // Wrap a long title onto 2 lines if needed
            const titleLines = doc.splitTextToSize(jobTitle, pageWidth - 2 * margin);
            doc.text(titleLines.slice(0, 2), margin, 44);
            doc.setFont('helvetica', 'normal');
            doc.setFontSize(9);
            _setText(doc, _BRAND.blue200);
            doc.text(
                'Generated ' + new Date().toLocaleString() + '   \u2022   ' +
                candidates.length + ' candidate' + (candidates.length === 1 ? '' : 's'),
                margin, 60
            );

            _setText(doc, _BRAND.slate900);
            let y = 80;
            if (data.query) {
                doc.setFont('helvetica', 'bold');
                doc.setFontSize(10);
                _setText(doc, _BRAND.blue700);
                doc.text('Job Description / Query', margin, y);
                y += 5;
                // Soft callout box for the query
                const qLines = doc.splitTextToSize(String(data.query), contentWidth - 8).slice(0, 8);
                const qBoxH = qLines.length * 4.5 + 6;
                _setFill(doc, _BRAND.blue50);
                doc.rect(margin, y, contentWidth, qBoxH, 'F');
                _setFill(doc, _BRAND.blue400);
                doc.rect(margin, y, 1.8, qBoxH, 'F');
                doc.setFont('helvetica', 'normal');
                doc.setFontSize(9);
                _setText(doc, _BRAND.slate800);
                let ty = y + 5;
                qLines.forEach(function (ln) { doc.text(ln, margin + 5, ty); ty += 4.5; });
                y += qBoxH + 7;
            }

            // -- Stat cards (4 in a row + avg-score chip) -----------------
            const metrics = data.hr_metrics || {};
            const strongN = metrics.strong_fits != null ? metrics.strong_fits : candidates.filter(function (c) { return c.score >= 80; }).length;
            const mediumN = metrics.medium_fits != null ? metrics.medium_fits : candidates.filter(function (c) { return c.score >= 60 && c.score < 80; }).length;
            const weakN   = metrics.weak_fits   != null ? metrics.weak_fits   : candidates.filter(function (c) { return c.score < 60; }).length;
            const avgScore = (candidates.reduce(function (s, c) { return s + c.score; }, 0) / candidates.length);

            const cardDefs = [
                { label: 'Total',           value: String(candidates.length), fill: _BRAND.blue50,    accent: _BRAND.blue600,    text: _BRAND.blue800 },
                { label: 'Strong Fits',     value: String(strongN),           fill: _BRAND.emerald50, accent: _BRAND.emerald600, text: _BRAND.emerald700, sub: '>= 80%' },
                { label: 'Medium Fits',     value: String(mediumN),           fill: _BRAND.amber50,   accent: _BRAND.amber600,   text: _BRAND.amber600,   sub: '60 - 79%' },
                { label: 'Weak Fits',       value: String(weakN),             fill: _BRAND.rose50,    accent: _BRAND.rose600,    text: _BRAND.rose700,    sub: '< 60%' },
            ];
            const gap = 4;
            const cardW = (contentWidth - gap * (cardDefs.length - 1)) / cardDefs.length;
            const cardH = 26;
            cardDefs.forEach(function (cd, i) {
                const cx = margin + i * (cardW + gap);
                _setFill(doc, cd.fill);
                doc.roundedRect(cx, y, cardW, cardH, 2.5, 2.5, 'F');
                _setFill(doc, cd.accent);
                doc.rect(cx, y, cardW, 1.6, 'F');
                doc.setFont('helvetica', 'bold');
                doc.setFontSize(18);
                _setText(doc, cd.text);
                doc.text(cd.value, cx + 4, y + 13);
                doc.setFont('helvetica', 'bold');
                doc.setFontSize(8.5);
                _setText(doc, _BRAND.slate700);
                doc.text(cd.label.toUpperCase(), cx + 4, y + 19);
                if (cd.sub) {
                    doc.setFont('helvetica', 'normal');
                    doc.setFontSize(7.5);
                    _setText(doc, _BRAND.slate500);
                    doc.text(cd.sub, cx + 4, y + 23.5);
                }
            });
            y += cardH + 5;

            // Avg score chip (full-width)
            const chipH = 10;
            _setFill(doc, _BRAND.slate50);
            doc.roundedRect(margin, y, contentWidth, chipH, 2, 2, 'F');
            doc.setFont('helvetica', 'bold');
            doc.setFontSize(9);
            _setText(doc, _BRAND.slate600);
            doc.text('AVERAGE MATCH SCORE', margin + 4, y + 6.5);
            doc.setFont('helvetica', 'bold');
            doc.setFontSize(11);
            const avgColor = _scoreColor(avgScore);
            doc.setTextColor(avgColor[0], avgColor[1], avgColor[2]);
            doc.text(avgScore.toFixed(1) + '%', margin + contentWidth - 4, y + 7, { align: 'right' });
            y += chipH + 8;

            // Ranked candidates table
            y = _drawSectionHeader(doc, 1, 'Ranked Candidates', y, pageWidth, margin);
            doc.autoTable({
                startY: y,
                margin: { left: margin, right: margin },
                head: [['#', 'Candidate', 'Position', 'Experience', 'Score', 'Status']],
                body: candidates.map(function (c, i) {
                    const ov = c.analysisData.candidate_overview || {};
                    const pos = (ov.position_applied_for && String(ov.position_applied_for).trim()) || jobTitle || '-';
                    return [
                        String(i + 1),
                        _safe(c.name, '-'),
                        pos,
                        _safe(ov.experience_years, '-'),
                        Math.round(c.score) + '%',
                        _safe(ov.match_status, '-'),
                    ];
                }),
                styles: { fontSize: 8.8, cellPadding: 2.2, lineColor: _BRAND.slate200, lineWidth: 0.15, textColor: _BRAND.slate800, overflow: 'linebreak' },
                headStyles: { fillColor: _BRAND.blue600, textColor: [255, 255, 255], fontStyle: 'bold' },
                alternateRowStyles: { fillColor: _BRAND.slate50 },
                columnStyles: {
                    0: { cellWidth: 9, halign: 'center', fontStyle: 'bold', textColor: _BRAND.slate500 },
                    1: { cellWidth: 48, fontStyle: 'bold', textColor: _BRAND.slate900 },
                    2: { cellWidth: 50 },
                    3: { cellWidth: 24 },
                    4: { cellWidth: 18, halign: 'center', fontStyle: 'bold' },
                    5: { cellWidth: contentWidth - 149 },
                },
                didParseCell: function (cell) {
                    if (cell.section === 'body' && cell.column.index === 4) {
                        const sc = parseInt(cell.cell.raw, 10);
                        if (!isNaN(sc)) {
                            const c = _scoreColor(sc);
                            cell.cell.styles.fillColor = c;
                            cell.cell.styles.textColor = [255, 255, 255];
                        }
                    }
                },
            });

            // One section per candidate on its own page. Track the page range
            // each candidate's section occupies so we can splice their resume
            // PDF in right after it during the merge step below.
            const introEndPage = doc.internal.getNumberOfPages();
            const sectionPageRanges = [];
            candidates.forEach(function (c) {
                const startPage = doc.internal.getNumberOfPages() + 1;
                _renderCandidateSection(doc, c.analysisData, c.name, { addPage: true, jobTitle: jobTitle });
                const endPage = doc.internal.getNumberOfPages();
                sectionPageRanges.push({ startPage: startPage, endPage: endPage });
            });

            _addPdfFooter(doc, 'Smart HR  \u2022  ' + jobTitle);

            const fileName = 'HR_Shortlist_' + (jobTitle.replace(/[^a-zA-Z0-9]+/g, '_')) + '_' + new Date().toISOString().split('T')[0] + '.pdf';

            // Build the merged PDF: report + each candidate's original resume
            // appended right after their section. Non-PDF resumes (docx/txt)
            // and unreachable files are skipped silently with a console note.
            const baseBytes = doc.output('arraybuffer');
            return _buildExportWithResumes(baseBytes, candidates, introEndPage, sectionPageRanges)
                .then(function (mergedBytes) {
                    const bytes = mergedBytes || new Uint8Array(baseBytes);
                    const blob = new Blob([bytes], { type: 'application/pdf' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = fileName;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    setTimeout(function () { URL.revokeObjectURL(url); }, 1500);
                    const attachedCount = (window.__lastExportAttachedCount || 0);
                    const msg = attachedCount > 0
                        ? ('Exported ' + fileName + ' (' + attachedCount + ' resume' + (attachedCount === 1 ? '' : 's') + ' attached)')
                        : ('Exported ' + fileName);
                    showNotification(msg, 'success');
                });
        })
        .catch(function (err) {
            console.error('Bulk PDF export failed:', err);
            showNotification('Could not generate bulk PDF: ' + (err && err.message ? err.message : 'unknown error'), 'error');
        });
}

// Fetch a candidate's resume from the backend and return its ArrayBuffer
// (only if the response is a PDF). Returns null on any failure so the
// export can continue gracefully.
function _fetchResumePdfBytes(filePath) {
    if (!filePath) return Promise.resolve(null);
    return fetch('/api/download-resume?file_path=' + encodeURIComponent(filePath), { credentials: 'same-origin' })
        .then(function (r) {
            if (!r.ok) return null;
            const ct = (r.headers.get('Content-Type') || '').toLowerCase();
            const lower = String(filePath).toLowerCase();
            const looksPdf = ct.indexOf('pdf') !== -1 || lower.endsWith('.pdf');
            if (!looksPdf) return null;
            return r.arrayBuffer();
        })
        .catch(function (e) {
            console.warn('Resume fetch failed for', filePath, e);
            return null;
        });
}

// Merge the report (jsPDF bytes) with each candidate's original PDF resume,
// inserted immediately after that candidate's section. Returns merged bytes,
// or null if pdf-lib is unavailable (caller falls back to the plain report).
function _buildExportWithResumes(baseBytes, candidates, introEndPage, sectionPageRanges) {
    window.__lastExportAttachedCount = 0;
    if (!window.PDFLib || !window.PDFLib.PDFDocument) {
        return Promise.resolve(null);
    }
    const PDFDocument = window.PDFLib.PDFDocument;
    return Promise.all(candidates.map(function (c) { return _fetchResumePdfBytes(c.filePath); }))
        .then(function (resumeBuffers) {
            return Promise.all([
                PDFDocument.load(baseBytes),
                PDFDocument.create(),
                Promise.resolve(resumeBuffers),
            ]);
        })
        .then(function (arr) {
            const basePdf = arr[0];
            const merged = arr[1];
            const resumeBuffers = arr[2];

            // Copy intro pages (cover, summary, ranked list) first.
            const introIdx = [];
            for (let i = 0; i < introEndPage; i++) introIdx.push(i);
            const chain = (introIdx.length
                ? merged.copyPages(basePdf, introIdx).then(function (pages) {
                    pages.forEach(function (p) { merged.addPage(p); });
                })
                : Promise.resolve());

            return chain.then(function () {
                // Sequentially copy each candidate's section then their resume.
                let p = Promise.resolve();
                candidates.forEach(function (c, i) {
                    const range = sectionPageRanges[i];
                    p = p.then(function () {
                        if (!range) return null;
                        const idxs = [];
                        for (let pg = range.startPage; pg <= range.endPage; pg++) idxs.push(pg - 1);
                        return merged.copyPages(basePdf, idxs).then(function (pages) {
                            pages.forEach(function (pg) { merged.addPage(pg); });
                        });
                    }).then(function () {
                        const buf = resumeBuffers[i];
                        if (!buf) return null;
                        return PDFDocument.load(buf, { ignoreEncryption: true })
                            .then(function (resPdf) {
                                const idxs = resPdf.getPageIndices();
                                return merged.copyPages(resPdf, idxs).then(function (pages) {
                                    pages.forEach(function (pg) { merged.addPage(pg); });
                                    window.__lastExportAttachedCount += 1;
                                });
                            })
                            .catch(function (e) {
                                console.warn('Could not embed resume for', c.name, e);
                            });
                    });
                });
                return p.then(function () { return merged.save(); });
            });
        })
        .catch(function (e) {
            console.warn('Resume merge failed, exporting report only:', e);
            return null;
        });
}
window.exportAllCandidatesReport = exportAllCandidatesReport;

// Helper function to show analysis modal
function showAnalysisModal(candidateName, analysisData) {
    // Create modal overlay
    const modalOverlay = document.createElement('div');
    modalOverlay.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
    modalOverlay.onclick = (e) => {
        if (e.target === modalOverlay) {
            document.body.removeChild(modalOverlay);
        }
    };

    // Create modal content
    const modalContent = document.createElement('div');
    modalContent.className = 'bg-white rounded-lg p-6 max-w-4xl max-h-[90vh] overflow-y-auto m-4';
    const esc = window.escapeHtml || ((value) => {
        const div = document.createElement('div');
        div.textContent = value == null ? '' : String(value);
        return div.innerHTML;
    });
    modalContent.innerHTML = `
        <div class="flex justify-between items-center mb-6">
            <h2 class="text-2xl font-bold text-gray-800">
                <i class="fas fa-user-circle mr-2"></i>
                Full Analysis: ${esc(candidateName)}
            </h2>
            <button onclick="this.closest('.fixed').remove()" class="text-gray-500 hover:text-gray-700">
                <i class="fas fa-times text-xl"></i>
            </button>
        </div>
        <div class="bg-gray-50 rounded-lg p-4">
            <pre class="text-sm text-gray-700 whitespace-pre-wrap">${esc(JSON.stringify(analysisData, null, 2))}</pre>
        </div>
    `;

    modalOverlay.appendChild(modalContent);
    document.body.appendChild(modalOverlay);
}

function getCandidateCardByName(candidateName) {
    return Array.from(document.querySelectorAll('.professional-resume-card'))
        .find((card) => card.dataset.candidateName === candidateName) || null;
}

function getCandidateCommentsTextarea(candidateName) {
    const card = getCandidateCardByName(candidateName);
    return card ? card.querySelector('.hr-comments-textarea') : null;
}

// HR Actions Functions
async function setCandidateStatus(candidateName, status, checkbox) {
    // Get the search result ID from the candidate card
    const candidateCard = checkbox.closest('.professional-resume-card');
    const searchResultId = candidateCard ? candidateCard.getAttribute('data-search-result-id') : null;

    // If checkbox is being unchecked, clear the status
    if (!checkbox.checked) {
        // Remove status from localStorage
        const candidateData = JSON.parse(localStorage.getItem('candidateStatuses') || '{}');
        delete candidateData[candidateName];
        localStorage.setItem('candidateStatuses', JSON.stringify(candidateData));

        // Save to database if we have search result ID
        if (searchResultId) {
            try {
                const formData = new FormData();
                formData.append('search_result_id', searchResultId);
                formData.append('candidate_name', candidateName);
                formData.append('action_type', status);
                formData.append('action_status', 'false');

                await fetch('/api/candidate-action', {
                    method: 'POST',
                    body: formData
                });
            } catch (error) {
                console.error('Error clearing candidate status in database:', error);
            }
        }

        console.log(`Candidate ${candidateName} status cleared`);
        return;
    }

    // Store the status in localStorage (or you can send to backend)
    const candidateData = JSON.parse(localStorage.getItem('candidateStatuses') || '{}');
    candidateData[candidateName] = {
        status: status,
        timestamp: new Date().toISOString(),
        updatedBy: 'HR User' // You can get actual user info
    };
    localStorage.setItem('candidateStatuses', JSON.stringify(candidateData));

    // Save to database if we have search result ID
    if (searchResultId) {
        try {
            const formData = new FormData();
            formData.append('search_result_id', searchResultId);
            formData.append('candidate_name', candidateName);
            formData.append('action_type', status);
            formData.append('action_status', 'true');

            const comments = getCandidateCommentsTextarea(candidateName);
            if (comments && comments.value) {
                formData.append('comments', comments.value);
            }

            await fetch('/api/candidate-action', {
                method: 'POST',
                body: formData
            });
        } catch (error) {
            console.error('Error saving candidate status to database:', error);
        }
    }

    // Update checkbox states (only one can be selected)
    await updateStatusCheckboxes(candidateName, status);

    // Show confirmation
    showStatusNotification(candidateName, status);

    // Refresh dashboard statistics to reflect the updated counts
    try {
        loadCandidateStatusCounts();
    } catch (err) {
        console.error('Failed to refresh candidate status counts:', err);
    }

    console.log(`Candidate ${candidateName} marked as ${status}`);
}

async function updateStatusCheckboxes(candidateName, activeStatus) {
    const candidateCard = getCandidateCardByName(candidateName);
    if (!candidateCard) {
        return;
    }
    const allCheckboxes = candidateCard.querySelectorAll('.hr-checkbox');

    const updatePromises = [];

    allCheckboxes.forEach(checkbox => {
        const checkboxStatus = checkbox.getAttribute('data-status');
        if (checkboxStatus === activeStatus) {
            checkbox.checked = true;
            return;
        }

        checkbox.checked = false;

        const searchResultId = candidateCard.getAttribute('data-search-result-id');
        if (searchResultId) {
            const updatePromise = (async () => {
                try {
                    const formData = new FormData();
                    formData.append('search_result_id', searchResultId);
                    formData.append('candidate_name', candidateName);
                    formData.append('action_type', checkboxStatus);
                    formData.append('action_status', 'false');

                    await fetch('/api/candidate-action', {
                        method: 'POST',
                        body: formData
                    });
                } catch (error) {
                    console.error(`Error unchecking ${checkboxStatus} status for ${candidateName}:`, error);
                }
            })();

            updatePromises.push(updatePromise);
        }
    });

    // Wait for all uncheck operations to complete
    if (updatePromises.length > 0) {
        await Promise.all(updatePromises);
    }
}

async function saveCandidateComment(candidateName, comment) {
    // Get the search result ID from the candidate card
    const textarea = getCandidateCommentsTextarea(candidateName);
    const candidateCard = textarea ? textarea.closest('.professional-resume-card') : null;
    const searchResultId = candidateCard ? candidateCard.getAttribute('data-search-result-id') : null;

    // Store the comment in localStorage (or you can send to backend)
    const candidateComments = JSON.parse(localStorage.getItem('candidateComments') || '{}');
    candidateComments[candidateName] = {
        comment: comment,
        timestamp: new Date().toISOString(),
        updatedBy: 'HR User' // You can get actual user info
    };
    localStorage.setItem('candidateComments', JSON.stringify(candidateComments));

    // Save to database if we have search result ID
    if (searchResultId) {
        try {
            // Get current status if any
            const candidateData = JSON.parse(localStorage.getItem('candidateStatuses') || '{}');
            const currentStatus = candidateData[candidateName]?.status;

            if (currentStatus) {
                const formData = new FormData();
                formData.append('search_result_id', searchResultId);
                formData.append('candidate_name', candidateName);
                formData.append('action_type', currentStatus);
                formData.append('action_status', 'true');
                formData.append('comments', comment);

                await fetch('/api/candidate-action', {
                    method: 'POST',
                    body: formData
                });
            }
        } catch (error) {
            console.error('Error saving candidate comment to database:', error);
        }
    }

    console.log(`Comment saved for ${candidateName}: ${comment}`);
}

function showStatusNotification(candidateName, status) {
    // Create notification
    const notification = document.createElement('div');
    notification.className = 'fixed top-4 right-4 z-50 bg-white border border-gray-200 rounded-lg shadow-lg p-4 max-w-sm';

    const statusConfig = {
        'selected': { color: 'text-green-600', bg: 'bg-green-50', icon: 'fas fa-check-circle' },
        'shortlisted': { color: 'text-yellow-600', bg: 'bg-yellow-50', icon: 'fas fa-star' },
        'rejected': { color: 'text-red-600', bg: 'bg-red-50', icon: 'fas fa-times-circle' },
        'interviewed': { color: 'text-blue-600', bg: 'bg-blue-50', icon: 'fas fa-calendar-check' },
        'hired': { color: 'text-purple-600', bg: 'bg-purple-50', icon: 'fas fa-user-check' }
    };

    const config = statusConfig[status] || statusConfig['selected']; // Fallback to 'selected' if status not found
    const esc = window.escapeHtml || ((value) => {
        const div = document.createElement('div');
        div.textContent = value == null ? '' : String(value);
        return div.innerHTML;
    });

    notification.innerHTML = `
        <div class="flex items-center">
            <div class="flex-shrink-0">
                <div class="w-8 h-8 ${config.bg} rounded-full flex items-center justify-center">
                    <i class="${config.icon} ${config.color} text-sm"></i>
                </div>
            </div>
            <div class="ml-3">
                <p class="text-sm font-medium text-gray-900">Status Updated</p>
                <p class="text-sm text-gray-500">${esc(candidateName)} marked as ${esc(status)}</p>
            </div>
            <button onclick="this.parentElement.parentElement.remove()" class="ml-4 text-gray-400 hover:text-gray-600">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;

    document.body.appendChild(notification);

    // Auto remove after 3 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 3000);
}

// Load saved statuses and comments when page loads
function loadCandidateData() {
    const statuses = JSON.parse(localStorage.getItem('candidateStatuses') || '{}');
    const comments = JSON.parse(localStorage.getItem('candidateComments') || '{}');

    // Apply saved statuses
    Object.keys(statuses).forEach(candidateName => {
        const status = statuses[candidateName].status;
        updateStatusCheckboxes(candidateName, status);
    });

    // Apply saved comments
    Object.keys(comments).forEach(candidateName => {
        const comment = comments[candidateName].comment;
        const textarea = getCandidateCommentsTextarea(candidateName);
        if (textarea) {
            textarea.value = comment;
        }
    });
}

// JD Builder Page Initialization
function initializeJDBuilderPage() {
    let selectedSkills = [];

    // Get DOM elements
    const generateBtn = document.getElementById('jd-generate-btn');
    const clearBtn = document.getElementById('jd-clear-btn');
    const copyBtn = document.getElementById('jd-copy-btn');
    const downloadBtn = document.getElementById('jd-download-btn');
    const saveBtn = document.getElementById('jd-save-btn');

    const skillInput = document.getElementById('jd-skill-input');
    const skillsList = document.getElementById('jd-skills-list');

    const preview = document.getElementById('jd-preview');
    const progress = document.getElementById('jd-progress');
    const progressText = document.getElementById('jd-progress-text');

    // Skills management
    function addSkill(skill) {
        if (skill && !selectedSkills.includes(skill)) {
            selectedSkills.push(skill);
            updateSkillsDisplay();
            updateStats();
        }
    }

    function removeSkill(skill) {
        selectedSkills = selectedSkills.filter(s => s !== skill);
        updateSkillsDisplay();
        updateStats();
    }

    function updateSkillsDisplay() {
        if (selectedSkills.length === 0) {
            skillsList.innerHTML = '<span class="text-gray-500 text-sm">Skills will appear here...</span>';
        } else {
            const esc = window.escapeHtml || ((value) => {
                const div = document.createElement('div');
                div.textContent = value == null ? '' : String(value);
                return div.innerHTML;
            });
            skillsList.innerHTML = selectedSkills.map((skill, skillIndex) => `
                <span class="inline-flex items-center px-3 py-1 rounded-full text-sm bg-blue-100 text-blue-800">
                    ${esc(skill)}
                    <button type="button" data-skill-index="${skillIndex}" class="ml-2 text-blue-600 hover:text-blue-800 js-remove-skill">
                        <i class="fas fa-times text-xs"></i>
                    </button>
                </span>
            `).join('');
            skillsList.querySelectorAll('.js-remove-skill').forEach((button) => {
                button.addEventListener('click', () => {
                    const index = Number(button.dataset.skillIndex);
                    if (Number.isInteger(index) && selectedSkills[index]) {
                        removeSkill(selectedSkills[index]);
                    }
                });
            });
        }

        // Make removeSkill globally accessible
        window.removeSkill = removeSkill;
    }

    function updateStats() {
        const content = preview.textContent || '';
        const wordCount = content.trim() ? content.split(/\s+/).length : 0;
        const skillCount = selectedSkills.length;

        document.getElementById('jd-word-count').textContent = wordCount;
        document.getElementById('jd-skill-count').textContent = skillCount;

        // Simple completeness calculation
        const jobTitle = document.getElementById('jd-job-title').value;
        const description = document.getElementById('jd-ai-input').value;
        let completeness = 0;

        if (jobTitle) completeness += 25;
        if (description) completeness += 25;
        if (skillCount > 0) completeness += 25;
        if (wordCount > 100) completeness += 25;

        document.getElementById('jd-completeness').textContent = completeness + '%';

        // Simple readability score (inverse of average word length)
        if (wordCount > 0) {
            const avgWordLength = content.length / wordCount;
            const readability = Math.max(1, Math.min(10, Math.round(15 - avgWordLength)));
            document.getElementById('jd-readability').textContent = readability + '/10';
        }
    }

    // Event listeners
    if (skillInput) {
        skillInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const skill = skillInput.value.trim();
                if (skill) {
                    addSkill(skill);
                    skillInput.value = '';
                }
            }
        });
    }



    if (generateBtn) {
        generateBtn.addEventListener('click', async () => {
            await generateJobDescription();
        });
    }



    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            clearAllFields();
        });
    }

    if (copyBtn) {
        copyBtn.addEventListener('click', () => {
            copyToClipboard();
        });
    }

    if (downloadBtn) {
        downloadBtn.addEventListener('click', () => {
            downloadJD();
        });
    }



    // API functions
    async function generateJobDescription() {
        const companyName = document.getElementById('jd-company-name').value;
        const companyDetails = document.getElementById('jd-company-details').value;
        const jobTitle = document.getElementById('jd-job-title').value;
        const department = document.getElementById('jd-department').value;
        const location = document.getElementById('jd-location').value;
        const experienceLevel = document.getElementById('jd-experience-level').value;
        const employmentType = document.getElementById('jd-employment-type').value;
        const description = document.getElementById('jd-ai-input').value;

        if (!jobTitle) {
            showNotification('Please enter a job title', 'error');
            return;
        }

        showProgress('Generating job description...');

        try {
            const formData = new FormData();
            formData.append('company_name', companyName);
            formData.append('company_details', companyDetails);
            formData.append('job_title', jobTitle);
            formData.append('department', department);
            formData.append('location', location);
            formData.append('experience_level', experienceLevel);
            formData.append('employment_type', employmentType);
            formData.append('description', description);
            formData.append('skills', JSON.stringify(selectedSkills));

            const response = await fetch('/api/generate-jd', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            function sanitizeGeneratedHtml(html) {
                const template = document.createElement('template');
                template.innerHTML = html || '';

                template.content.querySelectorAll('script, iframe, object, embed, link, meta, base, form, input, button').forEach((node) => node.remove());
                template.content.querySelectorAll('*').forEach((node) => {
                    Array.from(node.attributes).forEach((attr) => {
                        const name = attr.name.toLowerCase();
                        const value = (attr.value || '').trim().toLowerCase();
                        if (name.startsWith('on') || name === 'srcdoc' || name === 'style') {
                            node.removeAttribute(attr.name);
                        }
                        if ((name === 'href' || name === 'src' || name === 'xlink:href') && value.startsWith('javascript:')) {
                            node.removeAttribute(attr.name);
                        }
                    });
                });

                return template.innerHTML;
            }

            if (data.success) {
                // Clean up HTML response to remove any markdown code blocks
                let cleanedContent = data.job_description;
                if (cleanedContent.includes('```html')) {
                    cleanedContent = cleanedContent.replace(/```html\s*/g, '').replace(/```\s*$/g, '');
                }
                preview.innerHTML = sanitizeGeneratedHtml(cleanedContent);
                showNotification('Job description generated successfully!', 'success');
            } else {
                showNotification('Failed to generate job description: ' + data.error, 'error');
            }
        } catch (error) {
            console.error('Error generating JD:', error);
            showNotification('Error generating job description', 'error');
        } finally {
            hideProgress();
        }
    }



    function clearAllFields() {
        document.getElementById('jd-company-name').value = '';
        document.getElementById('jd-company-details').value = '';
        document.getElementById('jd-job-title').value = '';
        document.getElementById('jd-department').value = '';
        document.getElementById('jd-location').value = '';
        document.getElementById('jd-experience-level').value = '';
        document.getElementById('jd-employment-type').value = 'full-time';
        document.getElementById('jd-ai-input').value = '';
        selectedSkills = [];
        updateSkillsDisplay();
        preview.innerHTML = `
            <div class="text-center text-gray-500 mt-20">
                <i class="fas fa-file-contract text-4xl mb-4"></i>
                <p class="text-lg">Your job description will appear here</p>
                <p class="text-sm">Fill in the job information and use AI to generate content</p>
            </div>
        `;
        showNotification('All fields cleared', 'info');
    }

    function copyToClipboard() {
        const content = preview.textContent;
        if (content) {
            navigator.clipboard.writeText(content).then(() => {
                showNotification('Job description copied to clipboard!', 'success');
            }).catch(() => {
                showNotification('Failed to copy to clipboard', 'error');
            });
        } else {
            showNotification('No content to copy', 'error');
        }
    }

    function downloadJD() {
        const content = preview.innerHTML;
        const jobTitle = document.getElementById('jd-job-title').value || 'Job Description';

        if (!content || !content.trim() || content.includes('Your job description will appear here')) {
            showNotification('No content to download', 'error');
            return;
        }

        // Wrap the JD fragment in a self-contained, printable HTML document
        // with the same look as the in-app preview. Without this, opening
        // the downloaded file shows unstyled raw text because the preview
        // styling lives in the parent app's stylesheet.
        const safeTitle = String(jobTitle).replace(/[<>&"']/g, (c) => ({
            '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&#39;'
        })[c]);
        const generatedAt = new Date().toLocaleString();
        const fullDoc = [
            '<!DOCTYPE html>',
            '<html lang="en">',
            '<head>',
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            `<title>${safeTitle}</title>`,
            '<style>',
            '  :root { color-scheme: light; }',
            '  * { box-sizing: border-box; }',
            '  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; color: #1f2937; line-height: 1.6; max-width: 850px; margin: 2.5rem auto; padding: 0 1.5rem; background: #fff; }',
            '  h1 { font-size: 2rem; font-weight: 700; color: #111827; margin: 0 0 0.5rem 0; line-height: 1.2; }',
            '  h2 { font-size: 1.25rem; font-weight: 600; color: #1f2937; margin: 1.75rem 0 0.5rem 0; padding-bottom: 0.25rem; border-bottom: 1px solid #e5e7eb; }',
            '  h3 { font-size: 1.05rem; font-weight: 600; color: #374151; margin: 1rem 0 0.4rem 0; }',
            '  p { margin: 0 0 0.75rem 0; color: #374151; }',
            '  p.jd-meta { color: #6b7280; font-size: 0.9rem; margin-bottom: 1.25rem; }',
            '  ul { list-style: disc outside; padding-left: 1.5rem; margin: 0 0 1rem 0; }',
            '  li { margin-bottom: 0.35rem; color: #374151; }',
            '  strong { color: #111827; font-weight: 600; }',
            '  hr { border: 0; border-top: 1px solid #e5e7eb; margin: 1.25rem 0; }',
            '  .jd-footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #e5e7eb; color: #9ca3af; font-size: 0.8rem; text-align: center; }',
            '  @media print { body { margin: 0.5in; max-width: none; } h2 { page-break-after: avoid; } li { page-break-inside: avoid; } }',
            '</style>',
            '</head>',
            '<body>',
            content,
            `<div class="jd-footer">Generated ${generatedAt} · Smart HR JD Builder</div>`,
            '</body>',
            '</html>',
            ''
        ].join('\n');

        const blob = new Blob([fullDoc], { type: 'text/html;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${jobTitle.replace(/[^a-z0-9]+/gi, '_').replace(/^_+|_+$/g, '')}.html`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showNotification('Job description downloaded!', 'success');
    }

    function showProgress(message) {
        if (progress && progressText) {
            progressText.textContent = message;
            progress.classList.remove('hidden');
        }
    }

    function hideProgress() {
        if (progress) {
            progress.classList.add('hidden');
        }
    }

    // Initialize
    updateSkillsDisplay();
}

// Settings Page Initialization
function initializeSettingsPage() {
    loadUserInfo();
    loadCompanyInfo();
    loadUsers();
    initializeUserManagement();
}

// Load current user information
function loadUserInfo() {
    if (window.currentUser) {
        const displayNameInput = document.getElementById('display-name');
        const emailInput = document.getElementById('email-address');

        if (displayNameInput) displayNameInput.value = window.currentUser.full_name || '';
        if (emailInput) emailInput.value = window.currentUser.email || '';

        // Hide user management section if not tenant admin
        const userManagementSection = document.getElementById('user-management-section');
        if (window.currentUser.user_type !== 'tenant_admin' && window.currentUser.user_type !== 'super_admin') {
            if (userManagementSection) {
                userManagementSection.style.display = 'none';
            }
        }
    }
}

// Load company information
async function loadCompanyInfo() {
    const companyDetails = document.getElementById('company-details');

    if (!companyDetails) {
        return;
    }

    const escapeHtml = (value) => {
        const div = document.createElement('div');
        div.textContent = value == null ? '' : String(value);
        return div.innerHTML;
    };

    const formatNumber = (value) => {
        const number = Number(value);
        return Number.isFinite(number) ? number.toLocaleString() : 'N/A';
    };

    const renderCompanyRows = (company) => `
        <div class="space-y-3">
            <div class="flex justify-between gap-4">
                <span class="text-sm font-medium text-gray-700">Company Name:</span>
                <span class="text-sm text-gray-900 text-right">${escapeHtml(company.company_name || 'N/A')}</span>
            </div>
            <div class="flex justify-between gap-4">
                <span class="text-sm font-medium text-gray-700">Company Code:</span>
                <span class="text-sm text-gray-900 text-right">${escapeHtml(company.company_code || 'N/A')}</span>
            </div>
            <div class="flex justify-between gap-4">
                <span class="text-sm font-medium text-gray-700">Subscription:</span>
                <span class="text-sm text-gray-900 capitalize text-right">${escapeHtml(company.subscription_plan || 'Basic')}</span>
            </div>
            <div class="flex justify-between gap-4">
                <span class="text-sm font-medium text-gray-700">Max Users:</span>
                <span class="text-sm text-gray-900 text-right">${formatNumber(company.max_users)}</span>
            </div>
            <div class="flex justify-between gap-4">
                <span class="text-sm font-medium text-gray-700">Max Resumes:</span>
                <span class="text-sm text-gray-900 text-right">${formatNumber(company.max_resumes)}</span>
            </div>
            <div class="flex justify-between gap-4">
                <span class="text-sm font-medium text-gray-700">Max Searches:</span>
                <span class="text-sm text-gray-900 text-right">${formatNumber(company.max_searches)}</span>
            </div>
        </div>
    `;

    if (window.currentUser && window.currentUser.user_type === 'super_admin') {
        try {
            const response = await fetch('/api/companies');
            if (!response.ok) {
                throw new Error('Failed to load tenant companies');
            }

            const data = await response.json();
            const companies = data.companies || [];
            const activeCount = companies.filter(company => company.is_active).length;

            if (companies.length === 0) {
                companyDetails.innerHTML = `
                    <div class="text-center text-gray-500 py-4">
                        <i class="fas fa-building text-2xl text-gray-300 mb-2"></i>
                        <p class="text-sm">No tenant companies created yet</p>
                    </div>
                `;
                return;
            }

            companyDetails.innerHTML = `
                <div class="space-y-4">
                    <div class="flex justify-between gap-4">
                        <span class="text-sm font-medium text-gray-700">Tenant Companies:</span>
                        <span class="text-sm text-gray-900 text-right">${formatNumber(companies.length)} total, ${formatNumber(activeCount)} active</span>
                    </div>
                    <div class="space-y-3">
                        ${companies.slice(0, 5).map(company => `
                            <div class="border border-gray-200 rounded-lg p-3">
                                ${renderCompanyRows(company)}
                            </div>
                        `).join('')}
                        ${companies.length > 5 ? `<p class="text-xs text-gray-500">${formatNumber(companies.length - 5)} more companies are available in Manage Companies.</p>` : ''}
                    </div>
                </div>
            `;
            return;
        } catch (error) {
            console.error('Error loading tenant company information:', error);
            companyDetails.innerHTML = `
                <div class="text-center text-red-500 py-4">
                    <i class="fas fa-exclamation-triangle text-2xl text-red-300 mb-2"></i>
                    <p class="text-sm">Failed to load tenant company information</p>
                </div>
            `;
            return;
        }
    }

    if (window.currentUser && window.currentUser.company) {
        const company = window.currentUser.company;
        companyDetails.innerHTML = renderCompanyRows(company);
    } else {
        companyDetails.innerHTML = `
            <div class="text-center text-gray-500 py-4">
                <i class="fas fa-exclamation-triangle text-2xl text-gray-300 mb-2"></i>
                <p class="text-sm">No company information available</p>
            </div>
        `;
    }
}

// Load users for tenant admin
async function loadUsers() {
    const usersList = document.getElementById('users-list');

    try {
        const response = await fetch('/api/users');
        if (!response.ok) {
            throw new Error('Failed to load users');
        }

        const data = await response.json();
        displayUsers(data.users || []);
    } catch (error) {
        console.error('Error loading users:', error);
        usersList.innerHTML = `
            <div class="text-center text-red-500 py-4">
                <i class="fas fa-exclamation-triangle text-2xl text-red-300 mb-2"></i>
                <p class="text-sm">Failed to load users</p>
            </div>
        `;
    }
}

// Display users list
function displayUsers(users) {
    const usersList = document.getElementById('users-list');

    if (users.length === 0) {
        usersList.innerHTML = `
            <div class="text-center text-gray-500 py-4">
                <i class="fas fa-users text-2xl text-gray-300 mb-2"></i>
                <p class="text-sm">No users found</p>
            </div>
        `;
        return;
    }

    usersList.innerHTML = users.map(user => `
        <div class="flex items-center justify-between p-3 border border-gray-200 rounded-lg hover:bg-gray-50">
            <div class="flex items-center space-x-3">
                <div class="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                    <i class="fas fa-user text-blue-600"></i>
                </div>
                <div>
                    <p class="text-sm font-medium text-gray-900">${user.full_name}</p>
                    <p class="text-xs text-gray-500">${user.email}</p>
                    <span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getUserTypeColor(user.user_type)}">
                        ${getUserTypeLabel(user.user_type)}
                    </span>
                </div>
            </div>
            <div class="flex items-center space-x-2">
                <span class="text-xs text-gray-500">
                    ${user.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A'}
                </span>
                ${window.currentUser.user_type === 'super_admin' || window.currentUser.user_type === 'tenant_admin' ? `
                    <button onclick="editUser(${user.id})" class="text-blue-600 hover:text-blue-800 text-sm">
                        <i class="fas fa-edit"></i>
                    </button>
                ` : ''}
            </div>
        </div>
    `).join('');
}

// Get user type styling
function getUserTypeColor(userType) {
    switch (userType) {
        case 'super_admin':
            return 'bg-red-100 text-red-800';
        case 'tenant_admin':
            return 'bg-purple-100 text-purple-800';
        case 'tenant_user':
            return 'bg-green-100 text-green-800';
        default:
            return 'bg-gray-100 text-gray-800';
    }
}

// Get user type label
function getUserTypeLabel(userType) {
    switch (userType) {
        case 'super_admin':
            return 'Super Admin';
        case 'tenant_admin':
            return 'Tenant Admin';
        case 'tenant_user':
            return 'Tenant User';
        default:
            return 'User';
    }
}

// Initialize user management functionality
function initializeUserManagement() {
    const addUserBtn = document.getElementById('add-user-btn');
    if (addUserBtn) {
        addUserBtn.addEventListener('click', showAddUserModal);
    }
}

// Show add user modal
function showAddUserModal() {
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
    modal.innerHTML = `
        <div class="bg-white rounded-xl p-6 max-w-md w-full mx-4">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-lg font-semibold text-gray-900">Add New User</h3>
                <button onclick="this.closest('.fixed').remove()" class="text-gray-400 hover:text-gray-600">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            
            <form id="add-user-form" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Full Name</label>
                    <input type="text" id="new-user-name" required class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" placeholder="Enter full name">
                </div>
                
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Email Address</label>
                    <input type="email" id="new-user-email" required class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" placeholder="user@company.com">
                </div>
                
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Password</label>
                    <input type="password" id="new-user-password" required class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" placeholder="Enter password">
                </div>
                
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">User Type</label>
                    <select id="new-user-type" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent">
                        <option value="tenant_user">Tenant User</option>
                        ${window.currentUser.user_type === 'super_admin' ? '<option value="tenant_admin">Tenant Admin</option>' : ''}
                    </select>
                </div>
                
                <div class="flex space-x-3 pt-4">
                    <button type="button" onclick="this.closest('.fixed').remove()" class="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors">
                        Cancel
                    </button>
                    <button type="submit" class="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                        <i class="fas fa-plus mr-2"></i>Add User
                    </button>
                </div>
            </form>
        </div>
    `;

    document.body.appendChild(modal);

    // Handle form submission
    const form = document.getElementById('add-user-form');
    form.addEventListener('submit', handleAddUser);
}

// Handle add user form submission
async function handleAddUser(event) {
    event.preventDefault();

    const formData = new FormData();
    formData.append('full_name', document.getElementById('new-user-name').value);
    formData.append('email', document.getElementById('new-user-email').value);
    formData.append('password', document.getElementById('new-user-password').value);
    formData.append('user_type', document.getElementById('new-user-type').value);

    // Add company_id if current user has a company
    if (window.currentUser && window.currentUser.company) {
        formData.append('company_id', window.currentUser.company.company_id);
    }

    try {
        const response = await fetch('/api/users', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to create user');
        }

        const result = await response.json();

        // Close modal
        document.querySelector('.fixed').remove();

        // Show success message
        showNotification('User created successfully!', 'success');

        // Reload users list
        loadUsers();

    } catch (error) {
        console.error('Error creating user:', error);
        showNotification(error.message, 'error');
    }
}

// Edit user - opens a modal allowing role / name / email / status / password updates
async function editUser(userId) {
    try {
        const resp = await fetch('/api/users');
        if (!resp.ok) throw new Error('Failed to load users');
        const data = await resp.json();
        const target = (data.users || []).find(u => u.id === userId);
        if (!target) {
            showNotification('User not found', 'error');
            return;
        }

        const isSuper = window.currentUser && window.currentUser.user_type === 'super_admin';
        const types = isSuper
            ? ['super_admin', 'tenant_admin', 'tenant_user']
            : ['tenant_admin', 'tenant_user'];
        const typeOptions = types.map(t => `<option value="${t}" ${target.user_type === t ? 'selected' : ''}>${getUserTypeLabel(t)}</option>`).join('');
        const safeName = (target.full_name || '').replace(/"/g, '&quot;');
        const safeEmail = (target.email || '').replace(/"/g, '&quot;');

        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
        modal.innerHTML = `
            <div class="bg-white rounded-xl p-6 max-w-md w-full mx-4">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-lg font-semibold text-gray-900"><i class="fas fa-user-edit mr-2"></i>Edit User</h3>
                    <button type="button" onclick="this.closest('.fixed').remove()" class="text-gray-400 hover:text-gray-600"><i class="fas fa-times"></i></button>
                </div>
                <form id="edit-user-form" class="space-y-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                        <input type="text" name="full_name" value="${safeName}" required class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Email</label>
                        <input type="email" name="email" value="${safeEmail}" required class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">User Type</label>
                        <select name="user_type" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">${typeOptions}</select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">New Password <span class="text-gray-400 text-xs">(leave blank to keep)</span></label>
                        <input type="password" name="new_password" minlength="8" placeholder="At least 8 characters" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                    </div>
                    <div class="flex items-center">
                        <input type="checkbox" id="edit-user-active" name="is_active" value="true" ${target.is_active ? 'checked' : ''} class="mr-2">
                        <label for="edit-user-active" class="text-sm text-gray-700">Active</label>
                    </div>
                    <div class="flex space-x-3 pt-2">
                        <button type="button" onclick="this.closest('.fixed').remove()" class="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50">Cancel</button>
                        <button type="submit" class="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">Save Changes</button>
                    </div>
                </form>
            </div>`;
        document.body.appendChild(modal);

        modal.querySelector('#edit-user-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const fd = new FormData(e.target);
            const body = new URLSearchParams();
            body.append('full_name', fd.get('full_name') || '');
            body.append('email', fd.get('email') || '');
            body.append('user_type', fd.get('user_type') || '');
            body.append('is_active', fd.get('is_active') ? 'true' : 'false');
            const pw = fd.get('new_password');
            if (pw) body.append('new_password', pw);
            try {
                const r = await fetch(`/api/users/${userId}`, { method: 'PUT', body });
                const out = await r.json().catch(() => ({}));
                if (r.ok) {
                    showNotification('User updated successfully', 'success');
                    modal.remove();
                    if (typeof loadUsers === 'function') loadUsers();
                } else {
                    showNotification(out.detail || 'Failed to update user', 'error');
                }
            } catch (err) {
                console.error(err);
                showNotification('Network error', 'error');
            }
        });
    } catch (err) {
        console.error('editUser error', err);
        showNotification('Failed to open edit dialog', 'error');
    }
}

// Show notification
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 px-4 py-2 rounded-lg text-white z-50 ${type === 'success' ? 'bg-green-600' :
        type === 'error' ? 'bg-red-600' :
            'bg-blue-600'
        }`;
    notification.textContent = message;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.remove();
    }, 3000);
}

// User Dashboard Functions
function shouldShowRecruitmentDetailsBanner() {
    const user = window.currentUser;
    return !!user && (user.user_type === 'tenant_admin' || user.user_type === 'tenant_user');
}

function showRecruitmentDetailsBanner() {
    const resourceUsageSection = document.getElementById('resource-usage-section');
    if (!resourceUsageSection || !shouldShowRecruitmentDetailsBanner()) return false;

    resourceUsageSection.classList.remove('hidden');
    return true;
}

function initializeUserDashboard() {
    // Show loading state for all dashboard elements immediately
    showDashboardLoadingState();

    // Set current date
    const currentDateElement = document.getElementById('current-date');
    if (currentDateElement) {
        const currentDate = new Date().toLocaleDateString('en-US', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
        currentDateElement.textContent = currentDate;
    }

    // Show the recruitment-overview banner for tenant admins and tenant users.
    // Tenant admins still get richer numbers from /api/company-resource-usage;
    // tenant users get the same company-scoped data from /api/dashboard-stats.
    if (showRecruitmentDetailsBanner()) {
        loadResourceUsageData();
    }

    // Load data with a slight delay to show the loading state
    setTimeout(() => {
        // Load search history into the table
        loadSearchHistoryForDashboard();

        // Load candidate status counts
        loadCandidateStatusCounts();

        // Load upcoming events
        loadUpcomingEvents();
    }, 1500); // 1.5 second delay to show loading state
}

// Show loading state for dashboard elements
function showDashboardLoadingState() {
    // Set loading state for status cards
    const statusElements = ['selected-count', 'rejected-count', 'shortlisted-count', 'interviewed-count'];
    statusElements.forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.innerHTML = '<div class="animate-pulse flex justify-center"><div class="h-6 w-12 bg-gray-200 rounded"></div></div>';
        }
    });

    // Set loading state for search history table
    const searchHistoryTable = document.getElementById('search-history-table');
    if (searchHistoryTable) {
        searchHistoryTable.innerHTML = `
            <tr>
                <td colspan="4" class="py-8">
                    <div class="animate-pulse space-y-4">
                        <div class="h-4 bg-gray-200 rounded w-3/4 mx-auto"></div>
                        <div class="h-4 bg-gray-200 rounded w-2/3 mx-auto"></div>
                        <div class="h-4 bg-gray-200 rounded w-3/4 mx-auto"></div>
                        <div class="h-4 bg-gray-200 rounded w-1/2 mx-auto"></div>
                    </div>
                </td>
            </tr>
        `;
    }

    // Set loading state for upcoming events
    const upcomingEvents = document.getElementById('upcoming-events');
    if (upcomingEvents) {
        upcomingEvents.innerHTML = `
            <div class="animate-pulse space-y-4">
                <div class="h-16 bg-gray-200 rounded w-full"></div>
                <div class="h-16 bg-gray-200 rounded w-full"></div>
                <div class="h-16 bg-gray-200 rounded w-full"></div>
            </div>
        `;
    }
}

async function loadSearchHistoryForDashboard() {
    try {
        const response = await fetch('/api/search-history?limit=5', {
            method: 'GET',
            credentials: 'same-origin', // Ensure cookies are sent
            headers: {
                'Content-Type': 'application/json'
            }
        });
        if (response.ok) {
            const data = await response.json();
            displaySearchHistoryInTable(data.history || []);
        }
    } catch (error) {
        console.error('Error loading search history:', error);
        // Show empty state if API fails
        displaySearchHistoryInTable([]);
    }
}

function displaySearchHistoryInTable(searches) {
    const tableBody = document.getElementById('search-history-table');
    if (!tableBody) return;
    const esc = window.escapeHtml || ((value) => {
        const div = document.createElement('div');
        div.textContent = value == null ? '' : String(value);
        return div.innerHTML;
    });
    const attr = window.escapeAttr || esc;

    if (searches.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="4" class="py-8 text-center">
                    <div class="text-gray-500">
                        <i class="fas fa-search text-2xl mb-2"></i>
                        <p class="text-sm">No recent searches found</p>
                        <p class="text-xs text-gray-400 mt-1">Start searching for candidates to see your history here</p>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    tableBody.innerHTML = searches.map(search => {
        const date = new Date(search.search_timestamp);
        const resultBadgeClass = search.result_count > 10 ? 'bg-green-100 text-green-800' :
            search.result_count > 5 ? 'bg-yellow-100 text-yellow-800' :
                'bg-red-100 text-red-800';

        // Truncate long search queries for dashboard display
        const truncatedQuery = search.search_query.length > 60 ?
            search.search_query.substring(0, 60) + '...' :
            search.search_query;

        return `
            <tr>
                <td class="py-3 px-2">
                    <div class="flex items-center space-x-2">
                        <i class="fas fa-search text-blue-500 text-xs"></i>
                        <span class="text-sm font-medium text-gray-900" title="${attr(search.search_query)}">${esc(truncatedQuery)}</span>
                    </div>
                    ${search.job_title ? `<p class="text-xs text-gray-500 mt-1">${esc(search.job_title)}</p>` : ''}
                </td>
                <td class="py-3 px-2">
                    <span class="${resultBadgeClass} px-2 py-1 rounded-full text-xs font-medium">
                        ${search.result_count} matches
                    </span>
                </td>
                <td class="py-3 px-2">
                    <span class="text-sm text-gray-600">${date.toLocaleDateString()}</span>
                    <p class="text-xs text-gray-400">${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</p>
                </td>
                <td class="py-3 px-2">
                    <button type="button" data-search-id="${search.id}"
                            class="text-blue-600 hover:text-blue-800 text-xs font-medium">
                        View Results
                    </button>
                </td>
            </tr>
        `;
    }).join('');
    tableBody.querySelectorAll('[data-search-id]').forEach((button) => {
        button.addEventListener('click', () => {
            const searchId = Number(button.dataset.searchId);
            const search = searches.find((item) => Number(item.id) === searchId);
            if (search) {
                loadSavedSearch(search.id, search.search_query || '');
            }
        });
    });
}

async function loadCandidateStatusCounts() {
    try {
        const response = await fetch('/api/dashboard-stats');
        if (!response.ok) {
            throw new Error('Failed to fetch dashboard stats');
        }

        const data = await response.json();
        if (data.success) {
            const statusData = {
                selected: data.candidate_stats.selected || 0,
                rejected: data.candidate_stats.rejected || 0,
                shortlisted: data.candidate_stats.shortlisted || 0,
                interviewed: data.candidate_stats.interviewed || 0
            };

            updateCandidateStatusCards(statusData);

            // Activity stats (always populated, even when no actions taken)
            if (data.activity_stats) {
                updateActivityStatsCards(data.activity_stats);
            }

            // Also update trending skills if available
            if (data.trending_skills && data.trending_skills.length > 0) {
                updateTrendingSkills(data.trending_skills);
            }
        }
    } catch (error) {
        console.error('Error loading candidate status counts:', error);
        // Fall back to showing zeros
        updateCandidateStatusCards({
            selected: 0,
            rejected: 0,
            shortlisted: 0,
            interviewed: 0
        });
    }
}

function updateCandidateStatusCards(data) {
    const selectedElement = document.getElementById('selected-count');
    const rejectedElement = document.getElementById('rejected-count');
    const shortlistedElement = document.getElementById('shortlisted-count');
    const interviewedElement = document.getElementById('interviewed-count');

    if (selectedElement) selectedElement.textContent = data.selected;
    if (rejectedElement) rejectedElement.textContent = data.rejected;
    if (shortlistedElement) shortlistedElement.textContent = data.shortlisted;
    if (interviewedElement) interviewedElement.textContent = data.interviewed;
}

function updateActivityStatsCards(stats) {
    const fmt = (n) => (typeof n === 'number' ? n.toLocaleString() : (n || 0));
    const set = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = fmt(val);
    };
    set('activity-total-searches', stats.total_searches);
    set('activity-total-candidates', stats.total_candidates);
    set('activity-total-resumes', stats.total_resumes);

    // For super admins, show companies instead of users in the 4th card.
    const isSuperAdmin = !!(window.currentUser && window.currentUser.user_type === 'super_admin');
    const usersLabel = document.getElementById('activity-users-label');
    if (isSuperAdmin && (stats.total_companies || 0) > 0) {
        if (usersLabel) usersLabel.textContent = 'Companies';
        set('activity-total-users', stats.total_companies);
    } else {
        if (usersLabel) usersLabel.textContent = 'Users';
        set('activity-total-users', stats.total_users);
    }
}

function updateTrendingSkills(skills) {
    const trendingSkillsContainer = document.getElementById('trending-skills');
    if (!trendingSkillsContainer || !skills || skills.length === 0) return;

    const skillsHtml = skills.slice(0, 5).map((skill, index) => {
        const percentage = Math.max(20, 100 - (index * 15)); // Visual representation
        return `
            <div class="flex items-center justify-between py-2">
                <span class="text-sm font-medium text-gray-700 capitalize">${skill.skill}</span>
                <div class="flex items-center space-x-2">
                    <div class="w-16 bg-gray-200 rounded-full h-2">
                        <div class="bg-blue-600 h-2 rounded-full" style="width: ${percentage}%"></div>
                    </div>
                    <span class="text-xs text-gray-500">${skill.frequency}</span>
                </div>
            </div>
        `;
    }).join('');

    trendingSkillsContainer.innerHTML = skillsHtml;
}

async function loadUpcomingEvents() {
    try {
        const response = await fetch('/api/upcoming-events');
        if (!response.ok) {
            throw new Error('Failed to fetch upcoming events');
        }

        const data = await response.json();
        if (data.success) {
            updateUpcomingEvents(data.events || []);
        }
    } catch (error) {
        console.error('Error loading upcoming events:', error);
        // Show empty state if API fails
        updateUpcomingEvents([]);
    }
}

function updateUpcomingEvents(events) {
    const eventsContainer = document.getElementById('upcoming-events');
    if (!eventsContainer) return;

    if (events.length === 0) {
        eventsContainer.innerHTML = `
            <div class="text-center py-8 text-gray-500">
                <i class="fas fa-calendar text-2xl mb-2"></i>
                <p class="text-sm">No upcoming events</p>
            </div>
        `;
        return;
    }

    const eventsHtml = events.slice(0, 5).map(event => {
        const eventDate = new Date(event.date);
        const eventTypeColor = event.type === 'interviewed' ? 'border-green-500' : 'border-yellow-500';
        const eventIcon = event.type === 'interviewed' ? 'fa-video' : 'fa-user-check';

        return `
            <div class="flex items-start space-x-3 py-3 border-l-4 ${eventTypeColor} pl-3 mb-3">
                <div class="flex-shrink-0">
                    <div class="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                        <i class="fas ${eventIcon} text-blue-600 text-xs"></i>
                    </div>
                </div>
                <div class="flex-1 min-w-0">
                    <p class="text-sm font-medium text-gray-900 truncate">${event.title}</p>
                    <p class="text-xs text-gray-500">${event.position || 'Position not specified'}</p>
                    <p class="text-xs text-gray-400 mt-1">${eventDate.toLocaleDateString()}</p>
                </div>
            </div>
        `;
    }).join('');

    eventsContainer.innerHTML = eventsHtml;
}

async function loadResourceUsageData() {
    // Try the admin-only endpoint first (richer data); fall back to the
    // dashboard-stats endpoint that every authenticated user can hit.
    if (window.currentUser && window.currentUser.user_type === 'tenant_admin') {
        try {
            const response = await fetch('/api/company-resource-usage');
            if (response.ok) {
                const data = await response.json();
                if (data.success && data.resource_usage) {
                    updateResourceUsageDisplay(data.resource_usage);
                    return;
                }
            }
        } catch (error) {
            // ignore - try fallback below
        }
    }

    try {
        const response = await fetch('/api/dashboard-stats');
        if (response.ok) {
            const data = await response.json();
            if (data.success && data.resource_usage) {
                updateResourceUsageDisplay(data.resource_usage);
                return;
            }
        }
    } catch (error) {
        console.error('Error loading resource usage data:', error);
    }

    // Final fallback so the banner doesn't look broken
    updateResourceUsageDisplay({
        resumes: { current: 0, maximum: 1000, usage_percent: 0 },
        searches: { current: 0, maximum: 10000, usage_percent: 0 },
        users: { current: 0, maximum: 10 },
        subscription_plan: 'basic'
    });
}

function updateResourceUsageDisplay(resourceUsage) {
    // Update resume usage
    const resumeCurrent = document.getElementById('resume-current');
    const resumeMaximum = document.getElementById('resume-maximum');
    const resumeUsagePercent = document.getElementById('resume-usage-percent');
    const resumeProgressBar = document.getElementById('resume-progress-bar');

    if (resumeCurrent) resumeCurrent.textContent = resourceUsage.resumes.current || 0;
    if (resumeMaximum) resumeMaximum.textContent = resourceUsage.resumes.maximum || 1000;
    if (resumeUsagePercent) resumeUsagePercent.textContent = `${resourceUsage.resumes.usage_percent || 0}%`;
    if (resumeProgressBar) resumeProgressBar.style.width = `${resourceUsage.resumes.usage_percent || 0}%`;

    // Update search usage
    const searchCurrent = document.getElementById('search-current');
    const searchMaximum = document.getElementById('search-maximum');
    const searchUsagePercent = document.getElementById('search-usage-percent');
    const searchProgressBar = document.getElementById('search-progress-bar');

    if (searchCurrent) searchCurrent.textContent = resourceUsage.searches.current || 0;
    if (searchMaximum) searchMaximum.textContent = resourceUsage.searches.maximum || 10000;
    if (searchUsagePercent) searchUsagePercent.textContent = `${resourceUsage.searches.usage_percent || 0}%`;
    if (searchProgressBar) searchProgressBar.style.width = `${resourceUsage.searches.usage_percent || 0}%`;

    // Update subscription plan
    const subscriptionPlan = document.getElementById('subscription-plan');
    if (subscriptionPlan) {
        subscriptionPlan.textContent = (resourceUsage.subscription_plan || 'basic').toUpperCase();
    }

    // Update last updated time
    const lastUpdated = document.getElementById('last-updated');
    if (lastUpdated) {
        const now = new Date();
        lastUpdated.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    // Update progress bar colors based on usage
    if (resumeProgressBar) {
        const resumePercent = resourceUsage.resumes.usage_percent || 0;
        if (resumePercent >= 90) {
            resumeProgressBar.className = 'bg-red-400 rounded-full h-2 transition-all duration-300';
        } else if (resumePercent >= 75) {
            resumeProgressBar.className = 'bg-yellow-400 rounded-full h-2 transition-all duration-300';
        } else {
            resumeProgressBar.className = 'bg-white rounded-full h-2 transition-all duration-300';
        }
    }

    if (searchProgressBar) {
        const searchPercent = resourceUsage.searches.usage_percent || 0;
        if (searchPercent >= 90) {
            searchProgressBar.className = 'bg-red-400 rounded-full h-2 transition-all duration-300';
        } else if (searchPercent >= 75) {
            searchProgressBar.className = 'bg-yellow-400 rounded-full h-2 transition-all duration-300';
        } else {
            searchProgressBar.className = 'bg-white rounded-full h-2 transition-all duration-300';
        }
    }
}

function refreshSearchHistory() {
    loadSearchHistoryForDashboard();
    loadCandidateStatusCounts();

    // Show a brief loading indicator
    const refreshButton = event.target.closest('button');
    const originalHTML = refreshButton.innerHTML;
    refreshButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

    setTimeout(() => {
        refreshButton.innerHTML = originalHTML;
    }, 1000);
}

function loadMoreSearchHistory() {
    // Navigate to the full search history page
    loadPage('history');
}

function refreshUserDashboard() {
    // Show a brief loading indicator on the refresh button
    const refreshButton = event ? event.target.closest('button') : null;
    if (refreshButton) {
        const originalHTML = refreshButton.innerHTML;
        refreshButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

        // Reset after the dashboard data is loaded
        setTimeout(() => {
            refreshButton.innerHTML = originalHTML;
        }, 1500);
    }

    // Refresh dashboard data
    loadUserDashboardData();

    // Refresh resource usage banner if it's visible
    if (showRecruitmentDetailsBanner()) {
        loadResourceUsageData();
    }
}

function loadUserDashboardData() {
    // Show loading state first
    showDashboardLoadingState();

    // Load data with a slight delay to show the loading state
    setTimeout(() => {
        loadSearchHistoryForDashboard();
        loadCandidateStatusCounts();
        loadUpcomingEvents();
    }, 1500); // 1.5 second delay to show loading state
}

function showRecentSearches() {
    // Navigate to history page
    loadPage('history');
    setActiveLink(document.getElementById('history-link'));
}

// Interview Scheduling Functions
function scheduleInterview(candidateName, candidateEmail) {
    showInterviewScheduleModal(candidateName, candidateEmail);
}

// =============================================================================
// Dashboard stat-card click-through: list candidates by status
// =============================================================================
async function openCandidatesByStatus(status) {
    const mainContent = document.getElementById('main-content');
    if (!mainContent) return;

    const meta = {
        selected:    { title: 'Selected Candidates',    desc: 'Candidates marked ready to hire',           icon: 'fa-check-circle', color: 'emerald' },
        rejected:    { title: 'Rejected Candidates',    desc: 'Candidates you have rejected',              icon: 'fa-times-circle', color: 'red' },
        shortlisted: { title: 'Shortlisted Candidates', desc: 'Candidates awaiting review',                icon: 'fa-star',         color: 'yellow' },
        interviewed: { title: 'Interviewed Candidates', desc: 'Candidates with completed interviews',      icon: 'fa-video',        color: 'green' },
    }[status] || { title: 'Candidates', desc: '', icon: 'fa-users', color: 'gray' };

    const escFn = window.escapeHtml || ((v) => {
        const d = document.createElement('div');
        d.textContent = v == null ? '' : String(v);
        return d.innerHTML;
    });

    // Render shell with loading state immediately
    mainContent.innerHTML = `
        <div class="p-6 max-w-7xl mx-auto">
            <div class="mb-6 flex items-start justify-between">
                <div class="flex items-center space-x-4">
                    <div class="w-12 h-12 flex items-center justify-center rounded-xl bg-${meta.color}-100">
                        <i class="fas ${meta.icon} text-${meta.color}-600 text-2xl"></i>
                    </div>
                    <div>
                        <h2 class="text-2xl font-bold text-gray-900">${escFn(meta.title)}</h2>
                        <p class="text-sm text-gray-600">${escFn(meta.desc)}</p>
                    </div>
                </div>
                <button onclick="loadPage('dashboard')" class="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 border border-gray-300 rounded-lg hover:bg-gray-50">
                    <i class="fas fa-arrow-left mr-2"></i>Back to Dashboard
                </button>
            </div>

            <div id="candidates-by-status-body" class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <div class="animate-pulse space-y-3">
                    <div class="h-12 bg-gray-100 rounded"></div>
                    <div class="h-12 bg-gray-100 rounded"></div>
                    <div class="h-12 bg-gray-100 rounded"></div>
                </div>
            </div>
        </div>
    `;

    try {
        const resp = await fetch(`/api/candidates-by-status?status=${encodeURIComponent(status)}`, {
            credentials: 'same-origin',
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        renderCandidatesByStatusList(data.candidates || [], status, meta);
    } catch (err) {
        console.error('openCandidatesByStatus failed:', err);
        const body = document.getElementById('candidates-by-status-body');
        if (body) {
            body.innerHTML = `
                <div class="text-center py-12 text-gray-500">
                    <i class="fas fa-exclamation-triangle text-3xl text-red-400 mb-3"></i>
                    <p class="text-sm">Failed to load candidates: ${escFn(err.message || err)}</p>
                </div>
            `;
        }
    }
}

function renderCandidatesByStatusList(candidates, status, meta) {
    const body = document.getElementById('candidates-by-status-body');
    if (!body) return;
    const escFn = window.escapeHtml || ((v) => {
        const d = document.createElement('div');
        d.textContent = v == null ? '' : String(v);
        return d.innerHTML;
    });
    const attrFn = window.escapeAttr || escFn;

    if (!candidates.length) {
        body.innerHTML = `
            <div class="text-center py-16 text-gray-500">
                <i class="fas ${meta.icon} text-4xl text-gray-300 mb-4"></i>
                <p class="text-base font-medium">No ${escFn(status)} candidates yet</p>
                <p class="text-sm text-gray-400 mt-1">Action candidates from your search results to see them here.</p>
                <button onclick="loadPage('searchResumes')" class="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm">
                    <i class="fas fa-search mr-2"></i>Search Resumes
                </button>
            </div>
        `;
        return;
    }

    const rows = candidates.map((c) => {
        const score = Math.round(Number(c.match_score) || 0);
        const scoreBadge = score >= 75
            ? 'bg-green-100 text-green-800'
            : score >= 50 ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800';
        const actioned = c.actioned_at ? new Date(c.actioned_at).toLocaleDateString() : '';
        const contactBits = [];
        if (c.candidate_email) contactBits.push(`<i class="fas fa-envelope mr-1"></i>${escFn(c.candidate_email)}`);
        if (c.candidate_phone) contactBits.push(`<i class="fas fa-phone mr-1"></i>${escFn(c.candidate_phone)}`);
        if (c.candidate_location) contactBits.push(`<i class="fas fa-map-marker-alt mr-1"></i>${escFn(c.candidate_location)}`);
        const fileBase = (c.file_path || '').split('/').pop() || '';
        const srcId = c.search_id ? String(Number(c.search_id)) : '';
        return `
            <tr class="hover:bg-gray-50">
                <td class="py-3 px-3">
                    <div class="font-semibold text-gray-900">${escFn(c.candidate_name)}</div>
                    <div class="text-xs text-gray-500 mt-0.5">${contactBits.join(' &nbsp;·&nbsp; ')}</div>
                </td>
                <td class="py-3 px-3 text-sm text-gray-700">${escFn(c.position_applied || '—')}</td>
                <td class="py-3 px-3">
                    <span class="${scoreBadge} px-2 py-1 rounded-full text-xs font-medium">${score}%</span>
                </td>
                <td class="py-3 px-3 text-xs text-gray-500">${escFn(actioned)}</td>
                <td class="py-3 px-3 text-right">
                    <div class="inline-flex items-center space-x-2">
                        ${srcId ? `<button type="button" class="text-blue-600 hover:text-blue-800 text-xs font-medium" data-action="source" data-search-id="${attrFn(srcId)}" data-search-query="${attrFn(c.search_query || '')}" title="Open source search"><i class="fas fa-external-link-alt mr-1"></i>Source</button>` : ''}
                        ${fileBase ? `<button type="button" class="text-gray-600 hover:text-gray-900 text-xs font-medium" data-action="resume" data-file="${attrFn(fileBase)}" title="Download resume"><i class="fas fa-download mr-1"></i>Resume</button>` : ''}
                        <button type="button" class="text-emerald-700 hover:text-emerald-900 text-xs font-medium" data-action="schedule" data-name="${attrFn(c.candidate_name || '')}" data-email="${attrFn(c.candidate_email || '')}" title="Schedule with this candidate"><i class="fas fa-calendar-plus mr-1"></i>Schedule</button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');

    body.innerHTML = `
        <div class="flex items-center justify-between mb-4">
            <p class="text-sm text-gray-600">${candidates.length} candidate${candidates.length === 1 ? '' : 's'}</p>
        </div>
        <div class="overflow-x-auto">
            <table class="w-full">
                <thead>
                    <tr class="border-b border-gray-200">
                        <th class="text-left py-3 px-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Candidate</th>
                        <th class="text-left py-3 px-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Position</th>
                        <th class="text-left py-3 px-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Score</th>
                        <th class="text-left py-3 px-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Actioned</th>
                        <th class="text-right py-3 px-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-100">${rows}</tbody>
            </table>
        </div>
    `;

    // Delegated click handlers — avoids HTML-attribute quoting issues with
    // candidate names / file paths that contain quotes or apostrophes.
    body.querySelectorAll('button[data-action]').forEach((btn) => {
        btn.addEventListener('click', (ev) => {
            ev.preventDefault();
            const action = btn.getAttribute('data-action');
            try {
                if (action === 'source') {
                    const sid = Number(btn.getAttribute('data-search-id'));
                    const sq = btn.getAttribute('data-search-query') || '';
                    if (typeof loadSavedSearch === 'function' && sid) {
                        loadSavedSearch(sid, sq);
                    }
                } else if (action === 'resume') {
                    const file = btn.getAttribute('data-file') || '';
                    if (typeof downloadResume === 'function' && file) {
                        downloadResume(file);
                    }
                } else if (action === 'schedule') {
                    const name = btn.getAttribute('data-name') || '';
                    const email = btn.getAttribute('data-email') || '';
                    openGeneralScheduleModal(name, email);
                }
            } catch (err) {
                console.error('candidates-by-status row action failed:', action, err);
            }
        });
    });
}

// =============================================================================
// Schedule "+" button: open a generic schedule modal (no candidate context
// required). Reuses /api/schedule-interview on the backend.
// =============================================================================
function openGeneralScheduleModal(prefillName, prefillEmail) {
    const escFn = window.escapeHtml || ((v) => {
        const d = document.createElement('div');
        d.textContent = v == null ? '' : String(v);
        return d.innerHTML;
    });
    const attrFn = window.escapeAttr || escFn;
    const interviewerName = window.currentUser ? (window.currentUser.full_name || '') : '';

    // Remove any pre-existing schedule modal
    document.querySelectorAll('[data-modal="general-schedule"]').forEach((m) => m.remove());

    const modal = document.createElement('div');
    modal.setAttribute('data-modal', 'general-schedule');
    modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
    modal.innerHTML = `
        <div class="bg-white rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl max-h-[90vh] overflow-y-auto">
            <div class="flex items-center justify-between mb-6">
                <div>
                    <h3 class="text-lg font-semibold text-gray-900">Add to Schedule</h3>
                    <p class="text-sm text-gray-600 mt-1">Create a new interview or meeting</p>
                </div>
                <button type="button" onclick="closeGeneralScheduleModal()" class="text-gray-400 hover:text-gray-600">
                    <i class="fas fa-times text-lg"></i>
                </button>
            </div>

            <form id="general-schedule-form">
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-2">Candidate / Title <span class="text-red-500">*</span></label>
                    <input type="text" id="gs-candidate-name" required
                           class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                           value="${attrFn(prefillName || '')}"
                           placeholder="e.g., Jane Doe">
                </div>

                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-2">Candidate Email</label>
                    <input type="email" id="gs-candidate-email"
                           class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                           value="${attrFn(prefillEmail || '')}"
                           placeholder="optional">
                </div>

                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-2">Type</label>
                    <select id="gs-type" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                        <option value="phone">Phone Screening</option>
                        <option value="video" selected>Video Interview</option>
                        <option value="in-person">In-Person Interview</option>
                        <option value="technical">Technical Interview</option>
                        <option value="final">Final Interview</option>
                    </select>
                </div>

                <div class="grid grid-cols-2 gap-4 mb-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Date <span class="text-red-500">*</span></label>
                        <input type="date" id="gs-date" required
                               class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                               min="${new Date().toISOString().split('T')[0]}">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Time <span class="text-red-500">*</span></label>
                        <input type="time" id="gs-time" required
                               class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                    </div>
                </div>

                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-2">Duration</label>
                    <select id="gs-duration" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                        <option value="30">30 minutes</option>
                        <option value="45">45 minutes</option>
                        <option value="60" selected>1 hour</option>
                        <option value="90">1.5 hours</option>
                        <option value="120">2 hours</option>
                    </select>
                </div>

                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-2">Location / Platform</label>
                    <input type="text" id="gs-location"
                           class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                           placeholder="e.g., Zoom, Office Room A">
                </div>

                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-2">Auto-create online meeting</label>
                    <select id="gs-provider" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                        <option value="none" selected>No — use Location field</option>
                        <option value="meet">Google Meet (requires connected Google)</option>
                        <option value="teams">Microsoft Teams (requires connected Microsoft)</option>
                    </select>
                </div>

                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-2">Interviewer(s)</label>
                    <input type="text" id="gs-interviewer"
                           class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                           placeholder="e.g., John Smith"
                           value="${attrFn(interviewerName)}">
                </div>

                <div class="mb-4 flex items-start">
                    <input type="checkbox" id="gs-send-email" class="mt-1 mr-2">
                    <label for="gs-send-email" class="text-sm text-gray-700">
                        Email the candidate an interview invitation (requires email above)
                    </label>
                </div>

                <div class="mb-6">
                    <label class="block text-sm font-medium text-gray-700 mb-2">Notes</label>
                    <textarea id="gs-notes" rows="3"
                              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                              placeholder="Agenda, special instructions..."></textarea>
                </div>

                <div class="flex space-x-3">
                    <button type="button" onclick="closeGeneralScheduleModal()"
                            class="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors">Cancel</button>
                    <button type="submit"
                            class="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                        <i class="fas fa-calendar-plus mr-2"></i>Add to Schedule
                    </button>
                </div>
            </form>
        </div>
    `;

    document.body.appendChild(modal);

    // Defaults: tomorrow 10:00
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const dEl = document.getElementById('gs-date');
    const tEl = document.getElementById('gs-time');
    if (dEl) dEl.value = tomorrow.toISOString().split('T')[0];
    if (tEl) tEl.value = '10:00';

    const form = document.getElementById('general-schedule-form');
    if (form) form.addEventListener('submit', submitGeneralScheduleForm);
}

function closeGeneralScheduleModal() {
    document.querySelectorAll('[data-modal="general-schedule"]').forEach((m) => m.remove());
}

async function submitGeneralScheduleForm(event) {
    event.preventDefault();
    const v = (id) => (document.getElementById(id) || {}).value || '';
    const candidate_name = v('gs-candidate-name').trim();
    if (!candidate_name) {
        if (typeof showNotification === 'function') showNotification('Candidate / title is required', 'error');
        return;
    }

    const payload = {
        candidate_name,
        candidate_email: v('gs-candidate-email').trim(),
        interview_type:  v('gs-type') || 'video',
        interview_date:  v('gs-date'),
        interview_time:  v('gs-time'),
        duration:        v('gs-duration') || '60',
        location:        v('gs-location'),
        interviewer:     v('gs-interviewer'),
        notes:           v('gs-notes'),
        meeting_provider: v('gs-provider') || 'none',
        send_invite_email: !!(document.getElementById('gs-send-email') || {}).checked,
        created_by: window.currentUser ? window.currentUser.id : null,
    };

    const submitBtn = event.target.querySelector('button[type="submit"]');
    const originalText = submitBtn ? submitBtn.innerHTML : '';
    if (submitBtn) {
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Adding...';
        submitBtn.disabled = true;
    }

    try {
        const resp = await fetch('/api/schedule-interview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify(payload),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
            throw new Error(data.detail || `HTTP ${resp.status}`);
        }
        closeGeneralScheduleModal();
        if (typeof showNotification === 'function') {
            showNotification(`Added: ${payload.interview_type} with ${candidate_name} on ${payload.interview_date} ${payload.interview_time}`, 'success');
        }
        if (data && data.meeting && data.meeting.join_url) {
            if (typeof showNotification === 'function') showNotification(`Meeting link: ${data.meeting.join_url}`, 'info');
        }
        if (data && data.email && data.email.success) {
            if (typeof showNotification === 'function') showNotification('Invite email sent to candidate.', 'success');
        }
        // Refresh upcoming events list if on dashboard
        if (typeof loadUpcomingEvents === 'function') {
            try { loadUpcomingEvents(); } catch (_) { /* noop */ }
        }
    } catch (err) {
        console.error('submitGeneralScheduleForm failed:', err);
        if (typeof showNotification === 'function') {
            showNotification(`Failed to add to schedule: ${err.message || err}`, 'error');
        }
        if (submitBtn) {
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }
    }
}

function showInterviewScheduleModal(candidateName, candidateEmail) {
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
    const esc = window.escapeHtml || ((value) => {
        const div = document.createElement('div');
        div.textContent = value == null ? '' : String(value);
        return div.innerHTML;
    });
    const attr = window.escapeAttr || esc;
    const interviewerName = window.currentUser ? window.currentUser.full_name : '';
    modal.innerHTML = `
        <div class="bg-white rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl">
            <div class="flex items-center justify-between mb-6">
                <div>
                    <h3 class="text-lg font-semibold text-gray-900">Schedule Interview</h3>
                    <p class="text-sm text-gray-600 mt-1">with ${esc(candidateName)}</p>
                </div>
                <button onclick="closeInterviewModal()" class="text-gray-400 hover:text-gray-600">
                    <i class="fas fa-times text-lg"></i>
                </button>
            </div>
            
            <form id="interview-form">
                <!-- Interview Type -->
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-2">Interview Type</label>
                    <select id="interview-type" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                        <option value="phone">Phone Screening</option>
                        <option value="video">Video Interview</option>
                        <option value="in-person">In-Person Interview</option>
                        <option value="technical">Technical Interview</option>
                        <option value="final">Final Interview</option>
                    </select>
                </div>
                
                <!-- Date and Time -->
                <div class="grid grid-cols-2 gap-4 mb-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Date</label>
                        <input type="date" id="interview-date" 
                               class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                               min="${new Date().toISOString().split('T')[0]}" required>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-2">Time</label>
                        <input type="time" id="interview-time" 
                               class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" required>
                    </div>
                </div>
                
                <!-- Duration -->
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-2">Duration</label>
                    <select id="interview-duration" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                        <option value="30">30 minutes</option>
                        <option value="45">45 minutes</option>
                        <option value="60" selected>1 hour</option>
                        <option value="90">1.5 hours</option>
                        <option value="120">2 hours</option>
                    </select>
                </div>
                
                <!-- Location/Platform -->
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-2">Location/Platform</label>
                    <input type="text" id="interview-location" 
                           class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                           placeholder="e.g., Zoom, Office Conference Room A, Google Meet">
                </div>

                <!-- Online meeting provider (Teams / Meet / none) -->
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-2">Auto-create online meeting</label>
                    <select id="interview-provider" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                        <option value="none">No — use Location field above</option>
                        <option value="meet">Google Meet (requires connected Google account)</option>
                        <option value="teams">Microsoft Teams (requires connected Microsoft account)</option>
                    </select>
                    <p class="text-xs text-gray-500 mt-1">A join link will be generated and saved with the interview.</p>
                </div>

                <!-- Send candidate an invite email -->
                <div class="mb-4 flex items-start">
                    <input type="checkbox" id="interview-send-email" class="mt-1 mr-2"
                           ${candidateEmail ? 'checked' : 'disabled'}>
                    <label for="interview-send-email" class="text-sm text-gray-700">
                        Email the candidate an interview invitation
                        ${candidateEmail ? '' : '<span class="text-xs text-gray-400">(no email on file)</span>'}
                    </label>
                </div>
                
                <!-- Interviewer -->
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-2">Interviewer(s)</label>
                    <input type="text" id="interview-interviewer" 
                           class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                           placeholder="e.g., John Smith, Sarah Johnson"
                           value="${attr(interviewerName)}">
                </div>
                
                <!-- Notes -->
                <div class="mb-6">
                    <label class="block text-sm font-medium text-gray-700 mb-2">Notes</label>
                    <textarea id="interview-notes" 
                              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                              rows="3"
                              placeholder="Additional notes, agenda items, or special instructions..."></textarea>
                </div>
                
                <!-- Action Buttons -->
                <div class="flex space-x-3">
                    <button type="button" onclick="closeInterviewModal()" 
                            class="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors">
                        Cancel
                    </button>
                    <button type="submit" 
                            class="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                        <i class="fas fa-calendar-plus mr-2"></i>
                        Schedule Interview
                    </button>
                </div>
            </form>
        </div>
    `;

    document.body.appendChild(modal);

    // Set default date to tomorrow
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    document.getElementById('interview-date').value = tomorrow.toISOString().split('T')[0];

    // Set default time to 10:00 AM
    document.getElementById('interview-time').value = '10:00';

    const form = document.getElementById('interview-form');
    if (form) {
        form.addEventListener('submit', (event) => saveInterviewSchedule(event, candidateName, candidateEmail));
    }
}

function closeInterviewModal() {
    const modal = document.querySelector('.fixed.inset-0.bg-black');
    if (modal) {
        modal.remove();
    }
}

async function saveInterviewSchedule(event, candidateName, candidateEmail) {
    event.preventDefault();

    const formData = {
        candidate_name: candidateName,
        candidate_email: candidateEmail,
        interview_type: document.getElementById('interview-type').value,
        interview_date: document.getElementById('interview-date').value,
        interview_time: document.getElementById('interview-time').value,
        duration: document.getElementById('interview-duration').value,
        location: document.getElementById('interview-location').value,
        interviewer: document.getElementById('interview-interviewer').value,
        notes: document.getElementById('interview-notes').value,
        meeting_provider: (document.getElementById('interview-provider') || {}).value || 'none',
        send_invite_email: !!(document.getElementById('interview-send-email') || {}).checked,
        created_by: window.currentUser ? window.currentUser.id : null
    };

    try {
        // Show loading state
        const submitBtn = event.target.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Scheduling...';
        submitBtn.disabled = true;

        // Save to database
        const response = await fetch('/api/schedule-interview', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });

        if (response.ok) {
            const result = await response.json();

            // Close modal
            closeInterviewModal();

            // Show success notification
            showNotification(`Interview scheduled with ${candidateName} for ${formData.interview_date} at ${formData.interview_time}`, 'success');

            // Surface meeting / email outcomes (non-fatal)
            if (result && result.meeting && result.meeting.success === false && result.meeting.error) {
                showNotification(`Meeting link not created: ${result.meeting.error}`, 'warning');
            } else if (result && result.meeting && result.meeting.join_url) {
                showNotification(`Meeting link: ${result.meeting.join_url}`, 'info');
            }
            if (result && result.email && result.email.success === false && result.email.error) {
                showNotification(`Invite email not sent: ${result.email.error}`, 'warning');
            } else if (result && result.email && result.email.success) {
                showNotification('Invite email sent to candidate.', 'success');
            }

            // Update candidate status to interviewed
            const candidateCard = getCandidateCardByName(candidateName);
            const candidateCheckbox = candidateCard ? candidateCard.querySelector('input[data-status="interviewed"]') : null;
            if (candidateCheckbox) {
                candidateCheckbox.checked = true;
                await setCandidateStatus(candidateName, 'interviewed', candidateCheckbox);
            }
            else {
                // If no checkbox (e.g., card not loaded), persist status directly
                try {
                    const actionForm = new FormData();
                    actionForm.append('search_result_id', searchId || '');
                    actionForm.append('candidate_name', candidateName);
                    actionForm.append('action_type', 'interviewed');
                    actionForm.append('action_status', 'true');
                    await fetch('/api/candidate-action', { method: 'POST', body: actionForm });
                    loadCandidateStatusCounts();
                } catch (e) { console.error('Direct interviewed action save failed', e); }
            }

            // Refresh dashboard if we're on it
            if (window.location.pathname === '/dashboard' || document.getElementById('user-dashboard')) {
                loadUpcomingEvents();
            }

        } else {
            throw new Error('Failed to schedule interview');
        }

    } catch (error) {
        console.error('Error scheduling interview:', error);
        showNotification('Failed to schedule interview. Please try again.', 'error');

        // Reset button
        const submitBtn = event.target.querySelector('button[type="submit"]');
        submitBtn.innerHTML = '<i class="fas fa-calendar-plus mr-2"></i>Schedule Interview';
        submitBtn.disabled = false;
    }
}

// =============================================================================
// GLOBAL HANDLER SAFETY NET
// Many onclick="foo(...)" attributes in dynamically-rendered HTML need their
// targets on `window`. Functions defined inside DOMContentLoaded are NOT
// global by default. Re-export them defensively here. Also surface a
// diagnostic for any onclick name that resolves to undefined.
// =============================================================================
(function () {
    const handlerNames = [
        'showLoadingMessage', 'hideLoadingMessage', 'updateSearchProgress',
        'generateEnhancedResults', 'addUserMessage',
        'pollHRScorecardTask',
        'exportCandidateReport', 'exportAllCandidatesReport',
        'downloadResume', 'setCandidateStatus',
        'editUser', 'refreshSearchHistory',
        'scheduleInterview', 'closeInterviewModal',
        'loadPage', 'removeFile', 'closeAnalysisModal', 'removeSkill',
        'loadSavedSearch', 'showNotification', 'submitInterviewForm',
        'loadCandidateStatusCounts', 'loadUpcomingEvents',
        'openCandidatesByStatus', 'renderCandidatesByStatusList',
        'openGeneralScheduleModal', 'closeGeneralScheduleModal', 'submitGeneralScheduleForm',
    ];
    handlerNames.forEach(function (name) {
        try {
            // If a closure-scoped binding exists, eval pulls it; if it's
            // already on window, this is a no-op. Wrapped so a single missing
            // symbol does not break the rest.
            // eslint-disable-next-line no-eval
            const fn = (typeof window[name] === 'function')
                ? window[name]
                : (function () { try { return eval(name); } catch (_) { return undefined; } })();
            if (typeof fn === 'function' && typeof window[name] !== 'function') {
                window[name] = fn;
            }
        } catch (_) { /* noop */ }
    });

    // Diagnostic: log any onclick attribute whose primary identifier is not
    // resolvable on window. Helps catch new buttons that ship broken.
    function auditOnclickHandlers() {
        try {
            const els = document.querySelectorAll('[onclick]');
            const missing = new Set();
            els.forEach(function (el) {
                const code = el.getAttribute('onclick') || '';
                const m = code.match(/([A-Za-z_$][\w$]*)\s*\(/);
                if (m) {
                    const name = m[1];
                    if (typeof window[name] !== 'function'
                        && !['this', 'event', 'return', 'window'].includes(name)) {
                        missing.add(name);
                    }
                }
            });
            if (missing.size) {
                console.warn('[onclick-audit] missing global handlers:',
                    Array.from(missing));
            }
        } catch (e) { /* noop */ }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', auditOnclickHandlers);
    } else {
        // Defer one tick so dynamically-rendered cards are present.
        setTimeout(auditOnclickHandlers, 1500);
    }
})();
