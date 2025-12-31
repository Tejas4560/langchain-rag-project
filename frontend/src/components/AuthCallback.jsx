import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const AuthCallback = () => {
    const [searchParams] = useSearchParams();
    const { loginWithToken } = useAuth();
    const navigate = useNavigate();

    const [error, setError] = React.useState(null);

    useEffect(() => {
        const token = searchParams.get('token');
        const username = searchParams.get('username') || 'User'; // Fallback username if missing

        if (token) {
            try {
                loginWithToken(token, username);
                navigate('/');
            } catch (err) {
                console.error("Login failed:", err);
                setError("Failed to process login token.");
            }
        } else {
            console.error('Missing token or username in callback URL:', window.location.href);
            setError("Authentication failed. No token received from server.");
            // Do not immediately redirect, let user see the error
        }
    }, [searchParams, loginWithToken, navigate]);

    if (error) {
        return (
            <div style={{
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                alignItems: 'center',
                height: '100vh',
                backgroundColor: '#f3f4f6',
                color: '#ef4444'
            }}>
                <div style={{ padding: '2rem', backgroundColor: 'white', borderRadius: '8px', boxShadow: '0 4px 6px rgba(0,0,0,0.1)', textAlign: 'center' }}>
                    <h2 style={{ marginBottom: '1rem' }}>Login Error</h2>
                    <p>{error}</p>
                    <button
                        onClick={() => navigate('/login')}
                        style={{
                            marginTop: '1.5rem',
                            padding: '0.75rem 1.5rem',
                            backgroundColor: '#3b82f6',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: 'pointer'
                        }}
                    >
                        Return to Login
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '100vh',
            backgroundColor: '#f3f4f6'
        }}>
            <div style={{ textAlign: 'center' }}>
                <h2 style={{ fontSize: '1.5rem', marginBottom: '1rem' }}>Authenticating...</h2>
                <div style={{
                    border: '4px solid #f3f3f3',
                    borderTop: '4px solid #3498db',
                    borderRadius: '50%',
                    width: '40px',
                    height: '40px',
                    animation: 'spin 1s linear infinite',
                    margin: '0 auto'
                }}></div>
                <style>{`
                    @keyframes spin {
                        0% { transform: rotate(0deg); }
                        100% { transform: rotate(360deg); }
                    }
                `}</style>
            </div>
        </div>
    );
};

export default AuthCallback;
