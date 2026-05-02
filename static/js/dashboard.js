// Dashboard JavaScript

// Initialize dashboard
async function initDashboard() {
    await loadUserInfo();
    await loadDashboardData();
    setupEventListeners();
}

// Load user information
async function loadUserInfo() {
    try {
        const response = await fetch('/api/me');
        if (!response.ok) {
            window.location.href = '/login';
            return;
        }
        
        const data = await response.json();
        const user = data.user;
        
        // Update user info in header
        document.getElementById('currentUserName').textContent = user.full_name;
        document.getElementById('currentUserEmail').textContent = user.email;
        document.getElementById('currentUserType').textContent = user.user_type.replace('_', ' ').toUpperCase();
        
        // Store user data
        window.currentUser = user;
        
        // Show/hide sections based on user type
        updateUIForUserType(user.user_type);
        
        // Load initial dashboard data
        await loadDashboardData();
        
    } catch (error) {
        console.error('Error loading user info:', error);
    }
}

// Update UI based on user type
function updateUIForUserType(userType) {
    const superAdminSections = document.querySelectorAll('.super-admin-only');
    const tenantAdminSections = document.querySelectorAll('.tenant-admin-only');
    
    if (userType === 'super_admin') {
        superAdminSections.forEach(el => el.style.display = 'block');
        tenantAdminSections.forEach(el => el.style.display = 'block');
    } else if (userType === 'tenant_admin') {
        superAdminSections.forEach(el => el.style.display = 'none');
        tenantAdminSections.forEach(el => el.style.display = 'block');
    } else {
        // Regular users shouldn't be on dashboard
        window.location.href = '/';
    }
}

// Load dashboard data
async function loadDashboardData() {
    try {
        // Load different data based on user type
        if (window.currentUser.user_type === 'super_admin') {
            await loadSuperAdminData();
        } else if (window.currentUser.user_type === 'tenant_admin') {
            await loadTenantAdminData();
        }
    } catch (error) {
        console.error('Error loading dashboard data:', error);
    }
}

// Load super admin dashboard data
async function loadSuperAdminData() {
    try {
        // Load all companies
        const companiesResponse = await fetch('/api/companies');
        if (companiesResponse.ok) {
            const companiesData = await companiesResponse.json();
            displayCompanies(companiesData.companies || companiesData);
        }
        
        // Load all users
        const usersResponse = await fetch('/api/users');
        if (usersResponse.ok) {
            const usersData = await usersResponse.json();
            displayUsers(usersData.users || []);
        }
        
        // Load system stats
        const statsResponse = await fetch('/api/system-stats');
        if (statsResponse.ok) {
            const statsData = await statsResponse.json();
            displaySystemStats(statsData.stats || statsData);
        }
    } catch (error) {
        console.error('Error loading super admin data:', error);
    }
}

// Load tenant admin dashboard data
async function loadTenantAdminData() {
    try {
        // Load company users - use the same /api/users endpoint
        const usersResponse = await fetch('/api/users');
        if (usersResponse.ok) {
            const usersData = await usersResponse.json();
            displayUsers(usersData.users || []);
        }
        
        // Load company stats
        const statsResponse = await fetch('/api/company-stats');
        if (statsResponse.ok) {
            const statsData = await statsResponse.json();
            displayCompanyStats(statsData.stats || statsData);
        }
    } catch (error) {
        console.error('Error loading tenant admin data:', error);
    }
}

// Display companies table
function displayCompanies(companies) {
    const tbody = document.getElementById('companiesTableBody');
    if (!tbody) {
        console.error('Companies table body not found');
        return;
    }
    
    tbody.innerHTML = '';
    
    if (!companies || companies.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-4 text-center text-gray-500">No companies found</td></tr>';
        return;
    }
    
    companies.forEach(company => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap">
                <div class="text-sm font-medium text-gray-900">${company.company_name || 'N/A'}</div>
                <div class="text-sm text-gray-500">${company.company_code || 'N/A'}</div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                <div class="text-sm text-gray-900">${company.admin_name || 'No admin assigned'}</div>
                <div class="text-sm text-gray-500">${company.admin_email || ''}</div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                <div class="text-sm font-medium">${company.subscription_plan || 'basic'}</div>
                <div class="text-xs text-gray-400">Plan</div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                <div class="text-sm font-medium">${company.user_count || 0} users</div>
                <div class="flex space-x-4 text-xs text-gray-400 mt-1">
                    <span>${company.resume_count || 0} resumes</span>
                    <span>${company.search_count || 0} searches</span>
                </div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                    company.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                }">
                    ${company.is_active ? 'Active' : 'Inactive'}
                </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                <button onclick="viewCompanyDetails(${company.id})" class="text-blue-600 hover:text-blue-900 mr-3">View</button>
                <button onclick="editCompany(${company.id})" class="text-indigo-600 hover:text-indigo-900 mr-3">Edit</button>
                <button onclick="deleteCompany(${company.id})" class="text-red-600 hover:text-red-900">Delete</button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

// Display users table
function displayUsers(users) {
    const tbody = document.getElementById('usersTableBody');
    if (!tbody) {
        console.error('Users table body not found');
        return;
    }
    
    tbody.innerHTML = '';
    
    if (!users || users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-4 text-center text-gray-500">No users found</td></tr>';
        return;
    }
    
    users.forEach(user => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap">
                <div class="text-sm font-medium text-gray-900">${user.full_name || 'N/A'}</div>
                <div class="text-sm text-gray-500">${user.email || 'N/A'}</div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                    user.user_type === 'super_admin' ? 'bg-purple-100 text-purple-800' :
                    user.user_type === 'tenant_admin' ? 'bg-blue-100 text-blue-800' :
                    'bg-gray-100 text-gray-800'
                }">
                    ${user.user_type ? user.user_type.replace('_', ' ').toUpperCase() : 'N/A'}
                </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                ${user.company_name || 'System'}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                ${formatDate(user.last_login) || 'Never'}
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                    user.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                }">
                    ${user.is_active ? 'Active' : 'Inactive'}
                </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                <button onclick="viewUserDetails(${user.id})" class="text-blue-600 hover:text-blue-900 mr-3">View</button>
                <button onclick="editUser(${user.id})" class="text-indigo-600 hover:text-indigo-900 mr-3">Edit</button>
                <button onclick="deleteUser(${user.id})" class="text-red-600 hover:text-red-900">Delete</button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

// Setup event listeners
function setupEventListeners() {
    // Add company button
    const addCompanyBtn = document.getElementById('addCompanyBtn');
    if (addCompanyBtn) {
        addCompanyBtn.addEventListener('click', showAddCompanyModal);
    }
    
    // Add user button
    const addUserBtn = document.getElementById('addUserBtn');
    if (addUserBtn) {
        addUserBtn.addEventListener('click', showAddUserModal);
    }
    
    // Close modal buttons
    document.querySelectorAll('.close-modal').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.target.closest('.modal').classList.add('hidden');
        });
    });
}

// Show add company modal
function showAddCompanyModal() {
    document.getElementById('addCompanyModal').classList.remove('hidden');
}

// Show add user modal  
function showAddUserModal() {
    document.getElementById('addUserModal').classList.remove('hidden');
    
    // Load companies for dropdown if super admin
    if (window.currentUser.user_type === 'super_admin') {
        loadCompaniesForDropdown();
    }
}

// Load companies for dropdown
async function loadCompaniesForDropdown() {
    try {
        const response = await fetch('/api/companies');
        if (response.ok) {
            const companies = await response.json();
            const select = document.getElementById('userCompanyId');
            select.innerHTML = '<option value="">Select a company</option>';
            companies.forEach(company => {
                const option = document.createElement('option');
                option.value = company.id;
                option.textContent = company.company_name;
                select.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading companies:', error);
    }
}

// Submit add company form
async function submitAddCompany(event) {
    event.preventDefault();
    
    const formData = new FormData(event.target);
    
    try {
        const response = await fetch('/api/companies', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            showNotification('Company created successfully', 'success');
            document.getElementById('addCompanyModal').classList.add('hidden');
            event.target.reset();
            await loadSuperAdminData();
        } else {
            const error = await response.json();
            showNotification(error.detail || 'Error creating company', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showNotification('Error creating company', 'error');
    }
}

// Submit add user form
async function submitAddUser(event) {
    event.preventDefault();
    
    const formData = new FormData(event.target);
    
    try {
        const response = await fetch('/api/users', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            showNotification('User created successfully', 'success');
            document.getElementById('addUserModal').classList.add('hidden');
            event.target.reset();
            await loadDashboardData();
        } else {
            const error = await response.json();
            const errorMessage = error.detail || 'Error creating user';
            
            // Show specific error message for limits
            if (errorMessage.includes('maximum user limit')) {
                showNotification(errorMessage, 'error');
            } else {
                showNotification(errorMessage, 'error');
            }
        }
    } catch (error) {
        console.error('Error:', error);
        showNotification('Error creating user', 'error');
    }
}

// Show notification
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 p-4 rounded-lg text-white ${
        type === 'success' ? 'bg-green-500' :
        type === 'error' ? 'bg-red-500' :
        'bg-blue-500'
    } transition-opacity duration-300`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Display system stats (for super admin)
function displaySystemStats(stats) {
    try {
        document.getElementById('totalCompanies').textContent = stats.total_companies || 0;
        document.getElementById('totalUsers').textContent = stats.total_users || 0;
        document.getElementById('totalSearches').textContent = stats.total_searches || 0;
        document.getElementById('totalResumes').textContent = stats.total_resumes || 0;
    } catch (error) {
        console.error('Error displaying system stats:', error);
    }
}

// Display company stats (for tenant admin)
function displayCompanyStats(stats) {
    try {
        document.getElementById('totalUsers').textContent = stats.total_users || 0;
        document.getElementById('totalSearches').textContent = stats.total_searches || 0;
        document.getElementById('totalResumes').textContent = stats.total_resumes || 0;
        
        // Hide company-specific stats for tenant admin
        const companiesCard = document.getElementById('companiesCard');
        if (companiesCard) {
            companiesCard.style.display = 'none';
        }
    } catch (error) {
        console.error('Error displaying company stats:', error);
    }
}

// Utility function to format date
function formatDate(dateString) {
    if (!dateString) return null;
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

// Load companies data
async function loadCompanies() {
    try {
        const response = await fetch('/api/companies');
        if (response.ok) {
            const data = await response.json();
            displayCompanies(data.companies || []);
            
            // Update stats
            if (data.companies) {
                document.getElementById('totalCompanies').textContent = data.companies.length;
            }
        } else {
            console.error('Failed to load companies:', response.statusText);
            showNotification('Failed to load companies', 'error');
        }
    } catch (error) {
        console.error('Error loading companies:', error);
        showNotification('Error loading companies', 'error');
    }
}

// Load users data
async function loadUsers() {
    try {
        const response = await fetch('/api/users');
        if (response.ok) {
            const data = await response.json();
            displayUsers(data.users || []);
            
            // Update stats
            if (data.users) {
                document.getElementById('totalUsers').textContent = data.users.length;
            }
        } else {
            console.error('Failed to load users:', response.statusText);
            showNotification('Failed to load users', 'error');
        }
    } catch (error) {
        console.error('Error loading users:', error);
        showNotification('Error loading users', 'error');
    }
}

// View company details
function viewCompanyDetails(companyId) {
    showNotification('Company details view not implemented yet', 'info');
}

// Edit company
function editCompany(companyId) {
    showNotification('Company editing not implemented yet', 'info');
}

// Delete company
function deleteCompany(companyId) {
    if (confirm('Are you sure you want to delete this company? This action cannot be undone.')) {
        showNotification('Company deletion not implemented yet', 'info');
    }
}

// View user details
function viewUserDetails(userId) {
    showNotification('User details view not implemented yet', 'info');
}

// Edit user
function editUser(userId) {
    showNotification('User editing not implemented yet', 'info');
}

// Delete user
function deleteUser(userId) {
    if (confirm('Are you sure you want to delete this user? This action cannot be undone.')) {
        showNotification('User deletion not implemented yet', 'info');
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', initDashboard); 