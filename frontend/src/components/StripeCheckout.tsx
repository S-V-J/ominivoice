"use client";

import { useEffect, useState } from 'react';
import { loadStripe } from '@stripe/stripe-js';
import {
  Elements,
  PaymentElement,
  useStripe,
  useElements,
} from '@stripe/react-stripe-js';
import { api } from '../services/api';
import toast from 'react-hot-toast';
import { CreditCardIcon, ArrowLeftIcon } from '@heroicons/react/24/outline';

interface StripeCheckoutProps {
  plan: 'starter' | 'pro' | 'enterprise';
  onSuccess: () => void;
  onCancel: () => void;
}

const stripePromise = loadStripe(import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY || 'pk_test_your_key');

function CheckoutForm({ plan, onSuccess, onCancel }: StripeCheckoutProps) {
  const stripe = useStripe();
  const elements = useElements();
  const [loading, setLoading] = useState(false);
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function createCheckoutSession() {
      try {
        const data = await api.createCheckoutSession(plan);
        setClientSecret(data.client_secret);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to create checkout session');
        toast.error('Failed to initialize checkout');
      }
    }
    createCheckoutSession();
  }, [plan]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!stripe || !elements || !clientSecret) {
      return;
    }

    setLoading(true);
    setError(null);

    const { error: submitError } = await stripe.confirmPayment({
      elements,
      confirmParams: {
        return_url: `${window.location.origin}/account?success=true`,
      },
    });

    if (submitError) {
      setError(submitError.message || 'Payment failed');
      toast.error(submitError.message || 'Payment failed');
    } else {
      toast.success('Payment processing...');
      onSuccess();
    }

    setLoading(false);
  };

  if (!clientSecret) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary-600 border-t-transparent"></div>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Payment Method
        </label>
        <PaymentElement
          options={{
            layout: 'tabs',
          }}
        />
      </div>

      <div className="flex space-x-3">
        <button
          type="button"
          onClick={onCancel}
          className="btn-secondary flex-1"
          disabled={loading}
        >
          <ArrowLeftIcon className="w-5 h-5 mr-2" />
          Cancel
        </button>
        <button
          type="submit"
          className="btn-primary flex-1 flex items-center justify-center"
          disabled={loading || !stripe}
        >
          {loading ? (
            <>
              <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent mr-2"></div>
              Processing...
            </>
          ) : (
            <>
              <CreditCardIcon className="w-5 h-5 mr-2" />
              Subscribe to {plan.charAt(0).toUpperCase() + plan.slice(1)}
            </>
          )}
        </button>
      </div>
    </form>
  );
}

export default function StripeCheckout({ plan, onSuccess, onCancel }: StripeCheckoutProps) {
  const [clientSecret, setClientSecret] = useState<string | null>(null);

  useEffect(() => {
    async function createCheckoutSession() {
      try {
        const data = await api.createPaymentIntent(plan);
        setClientSecret(data.client_secret);
      } catch (err: any) {
        toast.error(err.response?.data?.detail || 'Failed to initialize checkout');
      }
    }
    createCheckoutSession();
  }, [plan]);

  if (!clientSecret) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary-600 border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto">
      <Elements stripe={stripePromise} options={{ clientSecret }}>
        <CheckoutForm plan={plan} onSuccess={onSuccess} onCancel={onCancel} />
      </Elements>
    </div>
  );
}