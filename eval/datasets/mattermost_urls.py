from pentest_bot.discovery.url import Route

MATTERMOST_ENDPOINTS = [
    # Backend API Routes (REST API) - Base URL: /api/v4/
    
    # User Routes
    Route("GET", "/api/v4/users"),
    Route("POST", "/api/v4/users"),
    Route("GET", "/api/v4/users/:user_id"),
    Route("PUT", "/api/v4/users/:user_id"),
    Route("DELETE", "/api/v4/users/:user_id"),
    Route("GET", "/api/v4/users/username/:username"),
    Route("GET", "/api/v4/users/email/:email"),
    Route("GET", "/api/v4/users/:user_id/teams"),
    Route("GET", "/api/v4/users/:user_id/teams/:team_id"),
    Route("GET", "/api/v4/users/:user_id/teams/:team_id/threads"),
    Route("GET", "/api/v4/users/:user_id/teams/:team_id/threads/:thread_id"),
    Route("GET", "/api/v4/users/:user_id/teams/members"),
    Route("GET", "/api/v4/users/:user_id/channels/:channel_id"),
    Route("GET", "/api/v4/users/:user_id/teams/:team_id/channels/members"),
    Route("GET", "/api/v4/users/:user_id/teams/:team_id/channels/categories"),
    Route("GET", "/api/v4/users/:user_id/posts"),
    Route("GET", "/api/v4/users/:user_id/posts/:post_id"),
    Route("GET", "/api/v4/users/:user_id/posts/:post_id/reactions/:emoji_name"),
    Route("GET", "/api/v4/users/:user_id/preferences"),
    
    # Bot Routes
    Route("GET", "/api/v4/bots"),
    Route("POST", "/api/v4/bots"),
    Route("GET", "/api/v4/bots/:bot_user_id"),
    Route("PUT", "/api/v4/bots/:bot_user_id"),
    Route("POST", "/api/v4/bots/:bot_user_id/disable"),
    Route("POST", "/api/v4/bots/:bot_user_id/enable"),
    Route("POST", "/api/v4/bots/:bot_user_id/convert_to_user"),
    Route("POST", "/api/v4/bots/:bot_user_id/assign/:user_id"),
    
    # Team Routes
    Route("GET", "/api/v4/teams"),
    Route("POST", "/api/v4/teams"),
    Route("GET", "/api/v4/teams/:team_id"),
    Route("PUT", "/api/v4/teams/:team_id"),
    Route("DELETE", "/api/v4/teams/:team_id"),
    Route("GET", "/api/v4/teams/name/:team_name"),
    Route("GET", "/api/v4/teams/:team_id/members"),
    Route("POST", "/api/v4/teams/:team_id/members"),
    Route("GET", "/api/v4/teams/:team_id/members/:user_id"),
    Route("PUT", "/api/v4/teams/:team_id/members/:user_id"),
    Route("DELETE", "/api/v4/teams/:team_id/members/:user_id"),
    Route("GET", "/api/v4/teams/:team_id/channels"),
    
    # Channel Routes
    Route("GET", "/api/v4/channels"),
    Route("POST", "/api/v4/channels"),
    Route("GET", "/api/v4/channels/:channel_id"),
    Route("PUT", "/api/v4/channels/:channel_id"),
    Route("DELETE", "/api/v4/channels/:channel_id"),
    Route("POST", "/api/v4/channels/direct"),
    Route("POST", "/api/v4/channels/group"),
    Route("POST", "/api/v4/channels/search"),
    Route("POST", "/api/v4/channels/group/search"),
    Route("GET", "/api/v4/teams/:team_id/channels/name/:channel_name"),
    Route("GET", "/api/v4/teams/name/:team_name/channels/name/:channel_name"),
    Route("GET", "/api/v4/channels/:channel_id/members"),
    Route("POST", "/api/v4/channels/:channel_id/members"),
    Route("GET", "/api/v4/channels/:channel_id/members/:user_id"),
    Route("PUT", "/api/v4/channels/:channel_id/members/:user_id"),
    Route("DELETE", "/api/v4/channels/:channel_id/members/:user_id"),
    Route("GET", "/api/v4/channels/:channel_id/moderations"),
    Route("GET", "/api/v4/channels/:channel_id/posts"),
    Route("GET", "/api/v4/channels/:channel_id/bookmarks"),
    Route("POST", "/api/v4/channels/:channel_id/bookmarks"),
    Route("PATCH", "/api/v4/channels/:channel_id/bookmarks/:bookmark_id"),
    Route("POST", "/api/v4/channels/:channel_id/bookmarks/:bookmark_id/sort_order"),
    Route("DELETE", "/api/v4/channels/:channel_id/bookmarks/:bookmark_id"),
    
    # Post Routes
    Route("GET", "/api/v4/posts"),
    Route("POST", "/api/v4/posts"),
    Route("GET", "/api/v4/posts/:post_id"),
    Route("PUT", "/api/v4/posts/:post_id"),
    Route("DELETE", "/api/v4/posts/:post_id"),
    
    # File Routes
    Route("GET", "/api/v4/files"),
    Route("POST", "/api/v4/files"),
    Route("GET", "/api/v4/files/:file_id"),
    Route("GET", "/files/:file_id/public"),
    
    # Upload Routes
    Route("GET", "/api/v4/uploads"),
    Route("POST", "/api/v4/uploads"),
    Route("GET", "/api/v4/uploads/:upload_id"),
    
    # Plugin Routes
    Route("GET", "/api/v4/plugins"),
    Route("POST", "/api/v4/plugins"),
    Route("GET", "/api/v4/plugins/:plugin_id"),
    Route("PUT", "/api/v4/plugins/:plugin_id"),
    Route("DELETE", "/api/v4/plugins/:plugin_id"),
    
    # Command Routes
    Route("GET", "/api/v4/commands"),
    Route("POST", "/api/v4/commands"),
    Route("GET", "/api/v4/commands/:command_id"),
    Route("PUT", "/api/v4/commands/:command_id"),
    Route("DELETE", "/api/v4/commands/:command_id"),
    
    # Webhook Routes
    Route("GET", "/api/v4/hooks"),
    Route("GET", "/api/v4/hooks/incoming"),
    Route("POST", "/api/v4/hooks/incoming"),
    Route("GET", "/api/v4/hooks/incoming/:hook_id"),
    Route("PUT", "/api/v4/hooks/incoming/:hook_id"),
    Route("DELETE", "/api/v4/hooks/incoming/:hook_id"),
    Route("GET", "/api/v4/hooks/outgoing"),
    Route("POST", "/api/v4/hooks/outgoing"),
    Route("GET", "/api/v4/hooks/outgoing/:hook_id"),
    Route("PUT", "/api/v4/hooks/outgoing/:hook_id"),
    Route("DELETE", "/api/v4/hooks/outgoing/:hook_id"),
    
    # OAuth Routes
    Route("GET", "/api/v4/oauth"),
    Route("GET", "/api/v4/oauth/apps"),
    Route("POST", "/api/v4/oauth/apps"),
    Route("GET", "/api/v4/oauth/apps/:app_id"),
    Route("PUT", "/api/v4/oauth/apps/:app_id"),
    Route("DELETE", "/api/v4/oauth/apps/:app_id"),
    Route("GET", "/api/v4/oauth/outgoing_connections"),
    Route("POST", "/api/v4/oauth/outgoing_connections"),
    Route("GET", "/api/v4/oauth/outgoing_connections/:outgoing_oauth_connection_id"),
    Route("PUT", "/api/v4/oauth/outgoing_connections/:outgoing_oauth_connection_id"),
    Route("DELETE", "/api/v4/oauth/outgoing_connections/:outgoing_oauth_connection_id"),
    
    # SAML Routes
    Route("GET", "/api/v4/saml"),
    Route("POST", "/api/v4/saml"),
    
    # System Routes
    Route("GET", "/api/v4/system"),
    Route("POST", "/api/v4/system"),
    
    # Compliance Routes
    Route("GET", "/api/v4/compliance"),
    Route("POST", "/api/v4/compliance"),
    
    # Cluster Routes
    Route("GET", "/api/v4/cluster"),
    Route("POST", "/api/v4/cluster"),
    
    # LDAP Routes
    Route("GET", "/api/v4/ldap"),
    Route("POST", "/api/v4/ldap"),
    
    # Elasticsearch Routes
    Route("GET", "/api/v4/elasticsearch"),
    Route("POST", "/api/v4/elasticsearch"),
    
    # Bleve Routes
    Route("GET", "/api/v4/bleve"),
    Route("POST", "/api/v4/bleve/purge_indexes"),
    
    # Data Retention Routes
    Route("GET", "/api/v4/data_retention"),
    Route("POST", "/api/v4/data_retention"),
    
    # Brand Routes
    Route("GET", "/api/v4/brand/image"),
    Route("POST", "/api/v4/brand/image"),
    Route("DELETE", "/api/v4/brand/image"),
    
    # Job Routes
    Route("GET", "/api/v4/jobs"),
    Route("POST", "/api/v4/jobs"),
    
    # License Routes
    Route("GET", "/api/v4/license"),
    Route("POST", "/api/v4/license"),
    
    # Public Routes
    Route("GET", "/api/v4/public"),
    
    # Reaction Routes
    Route("GET", "/api/v4/reactions"),
    Route("POST", "/api/v4/reactions"),
    
    # Role Routes
    Route("GET", "/api/v4/roles"),
    Route("POST", "/api/v4/roles"),
    
    # Scheme Routes
    Route("GET", "/api/v4/schemes"),
    Route("POST", "/api/v4/schemes"),
    
    # Emoji Routes
    Route("GET", "/api/v4/emoji"),
    Route("POST", "/api/v4/emoji"),
    Route("GET", "/api/v4/emoji/:emoji_id"),
    Route("PUT", "/api/v4/emoji/:emoji_id"),
    Route("DELETE", "/api/v4/emoji/:emoji_id"),
    Route("GET", "/api/v4/emoji/name/:emoji_name"),
    
    # Image Routes
    Route("GET", "/api/v4/image"),
    Route("POST", "/api/v4/image"),
    
    # Terms of Service Routes
    Route("GET", "/api/v4/terms_of_service"),
    Route("POST", "/api/v4/terms_of_service"),
    
    # Group Routes
    Route("GET", "/api/v4/groups"),
    Route("POST", "/api/v4/groups"),
    
    # Cloud Routes
    Route("GET", "/api/v4/cloud"),
    Route("POST", "/api/v4/cloud"),
    
    # Import/Export Routes
    Route("GET", "/api/v4/imports"),
    Route("POST", "/api/v4/imports"),
    Route("GET", "/api/v4/imports/:import_name"),
    Route("GET", "/api/v4/exports"),
    Route("POST", "/api/v4/exports"),
    Route("GET", "/api/v4/exports/:export_name"),
    
    # Remote Cluster Routes
    Route("GET", "/api/v4/remotecluster"),
    Route("POST", "/api/v4/remotecluster"),
    Route("GET", "/api/v4/sharedchannels"),
    Route("POST", "/api/v4/sharedchannels"),
    Route("GET", "/api/v4/remotecluster/:remote_id/channels/:channel_id"),
    Route("GET", "/api/v4/remotecluster/:remote_id/sharedchannelremotes"),
    
    # Permissions Routes
    Route("GET", "/api/v4/permissions"),
    Route("POST", "/api/v4/permissions"),
    
    # Usage Routes
    Route("GET", "/api/v4/usage"),
    Route("POST", "/api/v4/usage"),
    
    # Hosted Customer Routes
    Route("GET", "/api/v4/hosted_customer"),
    Route("POST", "/api/v4/hosted_customer"),
    
    # Drafts Routes
    Route("GET", "/api/v4/drafts"),
    Route("POST", "/api/v4/drafts"),
    
    # IP Filtering Routes
    Route("GET", "/api/v4/ip_filtering"),
    Route("POST", "/api/v4/ip_filtering"),
    
    # Reports Routes
    Route("GET", "/api/v4/reports"),
    Route("POST", "/api/v4/reports"),
    
    # Limits Routes
    Route("GET", "/api/v4/limits"),
    Route("POST", "/api/v4/limits"),
    
    # Custom Profile Attributes Routes
    Route("GET", "/api/v4/custom_profile_attributes"),
    Route("POST", "/api/v4/custom_profile_attributes"),
    Route("GET", "/api/v4/custom_profile_attributes/fields"),
    Route("POST", "/api/v4/custom_profile_attributes/fields"),
    Route("GET", "/api/v4/custom_profile_attributes/fields/:field_id"),
    Route("PUT", "/api/v4/custom_profile_attributes/fields/:field_id"),
    Route("DELETE", "/api/v4/custom_profile_attributes/fields/:field_id"),
    Route("GET", "/api/v4/custom_profile_attributes/values"),
    Route("POST", "/api/v4/custom_profile_attributes/values"),
    
    # Audit Logs Routes
    Route("GET", "/api/v4/audit_logs"),
    Route("POST", "/api/v4/audit_logs/certificate"),
    Route("DELETE", "/api/v4/audit_logs/certificate"),
    
    # Access Control Policy Routes
    Route("PUT", "/api/v4/access_control_policies"),
    Route("POST", "/api/v4/access_control_policies/search"),
    Route("POST", "/api/v4/access_control_policies/cel/check"),
    Route("POST", "/api/v4/access_control_policies/cel/test"),
    Route("GET", "/api/v4/access_control_policies/cel/autocomplete/fields"),
    Route("POST", "/api/v4/access_control_policies/cel/visual_ast"),
    Route("GET", "/api/v4/access_control_policies/:policy_id"),
    Route("DELETE", "/api/v4/access_control_policies/:policy_id"),
    Route("GET", "/api/v4/access_control_policies/:policy_id/activate"),
    Route("POST", "/api/v4/access_control_policies/:policy_id/assign"),
    Route("DELETE", "/api/v4/access_control_policies/:policy_id/unassign"),
    Route("GET", "/api/v4/access_control_policies/:policy_id/resources/channels"),
    Route("POST", "/api/v4/access_control_policies/:policy_id/resources/channels/search"),
    
    # Testing Routes (Development Only)
    Route("GET", "/manualtest"),
    Route("GET", "/api/v4/oauth_test"),
    
    # Frontend Routes (React Router) - Assuming GET method for all frontend routes
    Route("GET", "/login"),
    Route("GET", "/signup_user_complete"),
    Route("GET", "/reset_password"),
    Route("GET", "/reset_password_complete"),
    Route("GET", "/should_verify_email"),
    Route("GET", "/do_verify_email"),
    Route("GET", "/access_problem"),
    Route("GET", "/claim"),
    Route("GET", "/admin_console"),
    Route("GET", "/select_team"),
    Route("GET", "/create_team"),
    Route("GET", "/terms_of_service"),
    Route("GET", "/oauth/authorize"),
    Route("GET", "/error"),
    Route("GET", "/landing"),
    Route("GET", "/mfa"),
    Route("GET", "/preparing-workspace"),
    Route("GET", "/component_library"),
    Route("GET", "/:team_name"),
    Route("GET", "/:team_name/channels"),
    Route("GET", "/:team_name/channels/:channel_name"),
    Route("GET", "/:team_name/channels/:channel_name/pl/:post_id"),
    Route("GET", "/:team_name/messages"),
    Route("GET", "/:team_name/threads"),
    Route("GET", "/:team_name/drafts"),
    Route("GET", "/:team_name/integrations"),
    Route("GET", "/:team_name/emoji"),
    Route("GET", "/plug/:plugin_route"),
    Route("GET", "/_redirect/integrations/:subpath"),
    Route("GET", "/_redirect/pl/:postid"),
    
    # Web Routes (Non-API)
    # OAuth Web Routes
    Route("GET", "/oauth/authorize"),
    Route("POST", "/oauth/authorize"),
    Route("POST", "/oauth/deauthorize"),
    Route("POST", "/oauth/access_token"),
    Route("GET", "/oauth/:service/complete"),
    Route("GET", "/oauth/:service/login"),
    Route("GET", "/oauth/:service/mobile_login"),
    Route("GET", "/oauth/:service/signup"),
    
    # SAML Web Routes
    Route("GET", "/login/sso/saml"),
    Route("POST", "/login/sso/saml"),
    
    # Webhook Web Routes
    Route("POST", "/hooks/commands/:id"),
    Route("POST", "/hooks/:id"),
    
    # Static Web Routes
    Route("GET", "/robots.txt"),
    Route("GET", "/unsupported_browser.js"),
    
    # Legacy API Routes
    Route("GET", "/api/v3/oauth/:service/complete"),
    Route("GET", "/signup/:service/complete"),
    Route("GET", "/login/:service/complete"),
    
    # Debug Routes (Development/Metrics)
    Route("GET", "/debug"),
    Route("GET", "/debug/pprof/goroutine"),
    Route("GET", "/debug/pprof/heap"),
    Route("GET", "/debug/pprof/allocs"),
    Route("GET", "/debug/pprof/threadcreate"),
    Route("GET", "/debug/pprof/block"),
    Route("GET", "/debug/pprof/mutex"),
    
    # Catch-all Routes
    Route("GET", "/api/v4/*"),
    Route("GET", "/*"),
]