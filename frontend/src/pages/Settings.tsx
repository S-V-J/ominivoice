import { useState } from 'react';
import { useAuthStore } from '../store/authStore';
import { useAuth } from '../hooks/useAuth';
import toast from 'react-hot-toast';
import { UserCircleIcon, KeyIcon, BellIcon, CreditCardIcon } from '@heroicons/react/24/outline';

export default function Settings() {
  const { user, setUser } = useAuthStore();
  const { logout } = useAuth();
  const [activeTab, setActiveTab] = useState<'profile' | 'security' | 'billing' | 'notifications'>('profile');

  // Profile state
  const [profileEmail, setProfileEmail] = useState(user?.email || '');
  const [isUpdatingProfile, setIsUpdatingProfile] = useState(false);

  // Security state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isUpdatingPassword, setIsUpdatingPassword] = useState(false);

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsUpdatingProfile(true);
    try {
      // TODO: Implement profile update API
      // await api.updateProfile({ email: profileEmail });
      const updatedUser = { ...user!, email: profileEmail };
      setUser(updatedUser);
      toast.success('Profile updated');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update profile');
    } finally {
      setIsUpdatingProfile(false);
    }
  };

  const handleUpdatePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }
    if (newPassword.length < 8) {
      toast.error('Password must be at least 8 characters');
      return;
    }
    setIsUpdatingPassword(true);
    try {
      // TODO: Implement password change API
      // await api.changePassword({ current_password: currentPassword, new_password: newPassword });
      toast.success('Password updated');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update password');
    } finally {
      setIsUpdatingPassword(false);
    }
  };

  const handleSignOutAll = async () => {
    if (!confirm('Sign out of all devices? You will need to log in again.')) return;
    try {
      // TODO: Implement revoke all tokens API
      // await api.revokeAllTokens();
      logout();
      toast.success('Signed out of all devices');
    } catch (err: any) {
      toast.error('Failed to sign out');
    }
  };

  const tabs = [
    { id: 'profile', label: 'Profile', icon: UserCircleIcon },
    { id: 'security', label: 'Security', icon: KeyIcon },
    { id: 'billing', label: 'Billing', icon: CreditCardIcon },
    { id: 'notifications', label: 'Notifications', icon: BellIcon },
  ];

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Settings</h1>

      {/* Tab Navigation */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8" aria-label="Settings tabs">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === tab.id
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <tab.icon className="w-5 h-5" />
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'profile' && (
        <div className="card">
          <div className="card-header">
            <h2 className="text-lg font-semibold text-gray-900">Profile</h2>
            <p className="text-sm text-gray-500 mt-1">Manage your account profile</p>
          </div>
          <div className="card-body">
            <form onSubmit={handleUpdateProfile} className="space-y-6">
              <div>
                <label htmlFor="email" className="label">Email Address</label>
                <input
                  id="email"
                  type="email"
                  value={profileEmail}
                  onChange={(e) => setProfileEmail(e.target.value)}
                  className="input"
                  required
                />
              </div>
              <div>
                <label className="label">Plan</label>
                <div className="input bg-gray-50 cursor-default">
                  {user?.plan || 'free'}
                </div>
                <p className="text-xs text-gray-500 mt-1">Upgrade from the Billing tab</p>
              </div>
              <div>
                <label className="label">Member Since</label>
                <div className="input bg-gray-50 cursor-default">
                  {user?.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}
                </div>
              </div>
              <div className="pt-4 border-t border-gray-200">
                <button type="submit" disabled={isUpdatingProfile} className="btn-primary">
                  {isUpdatingProfile ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {activeTab === 'security' && (
        <div className="space-y-6">
          <div className="card">
            <div className="card-header">
              <h2 className="text-lg font-semibold text-gray-900">Change Password</h2>
            </div>
            <div className="card-body">
              <form onSubmit={handleUpdatePassword} className="space-y-4">
                <div>
                  <label htmlFor="current_password" className="label">Current Password</label>
                  <input
                    id="current_password"
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    className="input"
                    required
                  />
                </div>
                <div>
                  <label htmlFor="new_password" className="label">New Password</label>
                  <input
                    id="new_password"
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="input"
                    required
                    minLength={8}
                  />
                </div>
                <div>
                  <label htmlFor="confirm_password" className="label">Confirm New Password</label>
                  <input
                    id="confirm_password"
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="input"
                    required
                  />
                </div>
                <div className="pt-4 border-t border-gray-200">
                  <button type="submit" disabled={isUpdatingPassword} className="btn-primary">
                    {isUpdatingPassword ? 'Updating...' : 'Update Password'}
                  </button>
                </div>
              </form>
            </div>
          </div>

          <div className="card border-red-200">
            <div className="card-header">
              <h2 className="text-lg font-semibold text-gray-900">Sessions</h2>
            </div>
            <div className="card-body">
              <p className="text-gray-600 mb-4">Manage your active login sessions</p>
              <button onClick={handleSignOutAll} className="btn-ghost text-red-600 hover:bg-red-50">
                Sign Out of All Devices
              </button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'billing' && (
        <div className="card">
          <div className="card-header">
            <h2 className="text-lg font-semibold text-gray-900">Billing & Subscription</h2>
          </div>
          <div className="card-body">
            <div className="text-center py-12">
              <CreditCardIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">Billing Integration Coming Soon</h3>
              <p className="text-gray-500 mb-6">
                Stripe integration for subscription management, usage tracking, and invoice history
                will be available in a future release.
              </p>
              <div className="bg-gray-50 rounded-lg p-4 max-w-md mx-auto text-left">
                <p className="font-medium text-gray-900 mb-2">Current Plan: <span className="font-normal capitalize">{user?.plan || 'free'}</span></p>
                <p className="text-sm text-gray-600">Free tier includes:</p>
                <ul className="text-sm text-gray-600 space-y-1 ml-4">
                  <li>• Up to 3 voice agents</li>
                  <li>• 100 test call minutes/month</li>
                  <li>• Basic prompt templates</li>
                  <li>• Community support</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'notifications' && (
        <div className="card">
          <div className="card-header">
            <h2 className="text-lg font-semibold text-gray-900">Notifications</h2>
          </div>
          <div className="card-body">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-gray-900">Email Notifications</p>
                  <p className="text-sm text-gray-500">Receive email updates about your agents and calls</p>
                </div>
                <input type="checkbox" defaultChecked className="h-5 w-5 text-primary-600 rounded border-gray-300" />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-gray-900">Call Completion Alerts</p>
                  <p className="text-sm text-gray-500">Get notified when test calls complete</p>
                </div>
                <input type="checkbox" defaultChecked className="h-5 w-5 text-primary-600 rounded border-gray-300" />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-gray-900">Usage Reports</p>
                  <p className="text-sm text-gray-500">Weekly summary of agent usage and performance</p>
                </div>
                <input type="checkbox" className="h-5 w-5 text-primary-600 rounded border-gray-300" />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-gray-900">Security Alerts</p>
                  <p className="text-sm text-gray-500">Important security notifications (cannot be disabled)</p>
                </div>
                <input type="checkbox" defaultChecked disabled className="h-5 w-5 text-primary-600 rounded border-gray-300" />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}