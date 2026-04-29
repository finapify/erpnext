// Finapify Dashboard JavaScript

odoo.define('finapify.dashboard', ['web.core'], function(require) {
    'use strict';

    const core = require('web.core');
    
    // Dashboard initialization
    $(document).ready(function() {
        loadDashboardData();
        setupCardClickHandlers();
    });

    /**
     * Load dashboard statistics and data
     */
    function loadDashboardData() {
        $.ajax({
            url: '/finapify/dashboard/data',
            type: 'GET',
            dataType: 'json',
            success: function(response) {
                if (response.success) {
                    updateDashboardStats(response.data);
                } else {
                    console.error('Failed to load dashboard data:', response.error);
                }
            },
            error: function(error) {
                console.error('Dashboard data loading error:', error);
            }
        });
    }

    /**
     * Update dashboard statistics on the page
     */
    function updateDashboardStats(data) {
        $('.finapify-stat-connections').text(data.total_connections || 0);
        $('.finapify-stat-pending').text(data.pending_requests || 0);
        $('.finapify-stat-completed').text(data.completed_batches || 0);

        // Log loaded data
        console.log('Dashboard stats loaded:', data);
    }

    /**
     * Setup click handlers for quick access cards
     */
    function setupCardClickHandlers() {
        // Handle card button clicks
        $('[data-action]').on('click', function(e) {
            e.preventDefault();
            const action = $(this).data('action');
            if (action) {
                navigateToAction(action);
            }
        });

        // Handle card title clicks
        $('.dashboard-card .card-title a').on('click', function(e) {
            e.preventDefault();
            const action = $(this).closest('[data-action]').data('action');
            if (action) {
                navigateToAction(action);
            }
        });
    }

    /**
     * Navigate to Odoo action
     */
    function navigateToAction(actionId) {
        const actionMap = {
            'action_finapify_connection': 7,
            'action_finapify_payment_request': 9,
            'action_finapify_payment_batch': 10,
            'action_finapify_vendor_bank_map': 8,
            'action_finapify_journal_map': 6,
            'action_finapify_reconciliation': 11,
            'action_finapify_log': 12,
        };

        const actionNumber = actionMap[actionId];
        if (actionNumber) {
            window.location.href = '/web#action=' + actionNumber;
        } else {
            // Try direct navigation if action number is not in map
            window.location.href = '/web#action=' + actionId;
        }
    }

    /**
     * Authenticate with Finapify API
     */
    function authenticateFinapify(apiKey, apiSecret) {
        return $.ajax({
            url: '/finapify/dashboard/authenticate',
            type: 'POST',
            dataType: 'json',
            data: JSON.stringify({
                api_key: apiKey,
                api_secret: apiSecret
            }),
            contentType: 'application/json',
            success: function(response) {
                return response;
            },
            error: function(error) {
                console.error('Authentication error:', error);
                return {
                    success: false,
                    error: 'Authentication failed'
                };
            }
        });
    }

    // Export functions for external use
    window.FinapifyDashboard = {
        loadDashboardData: loadDashboardData,
        setupCardClickHandlers: setupCardClickHandlers,
        navigateToAction: navigateToAction,
        authenticateFinapify: authenticateFinapify
    };

    return {
        loadDashboardData: loadDashboardData,
        setupCardClickHandlers: setupCardClickHandlers,
        navigateToAction: navigateToAction,
        authenticateFinapify: authenticateFinapify
    };
});
