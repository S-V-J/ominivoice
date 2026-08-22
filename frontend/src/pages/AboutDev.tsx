import { useEffect, useState } from 'react';
import {
  CodeBracketIcon,
  CubeIcon,
  BookOpenIcon,
  HeartIcon,
  LinkIcon,
} from '@heroicons/react/24/outline';

export default function AboutDev() {
  const [changelog, setChangelog] = useState<string>('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Try to fetch changelog from a local file or use default
    fetch('/changelog.md')
      .then(res => res.text())
      .then(text => setChangelog(text))
      .catch(() => {
        setChangelog(defaultChangelog);
      })
      .finally(() => setLoading(false));
  }, []);

  const defaultChangelog = `# Changelog

## v0.1.0 (2026-08-17)
- Initial release of OminiVoice
- Multi-tenant voice agent configuration platform
- Simulated call testing via WebRTC
- AI-powered prompt rewriting
- Dual-stack voice engine (Local + NVIDIA NIM)

---

## Upcoming
- Cold-call queue management
- Stripe billing integration
- Real telephony adapter support
`;

  const openSourceComponents = [
    {
      name: 'FastAPI',
      url: 'https://fastapi.tiangolo.com/',
      license: 'MIT',
      description: 'Modern, fast web framework for building APIs with Python 3.7+',
    },
    {
      name: 'Pipecat',
      url: 'https://github.com/pipecat-ai/pipecat',
      license: 'BSD-2',
      description: 'Open-source framework for real-time voice AI pipelines',
    },
    {
      name: 'FastRTC',
      url: 'https://github.com/huggingface/fastrtc',
      license: 'Apache-2.0',
      description: 'WebRTC streaming for ML demos and applications',
    },
    {
      name: 'faster-whisper',
      url: 'https://github.com/SYSTRAN/faster-whisper',
      license: 'MIT',
      description: 'Fast speech recognition using CTranslate2',
    },
    {
      name: 'Kokoro-82M',
      url: 'https://github.com/hexgrad/kokoro',
      license: 'Apache-2.0',
      description: 'Small, fast, high-quality TTS model',
    },
    {
      name: 'Piper TTS',
      url: 'https://github.com/rhasspy/piper',
      license: 'MIT',
      description: 'Fast, local neural text-to-speech',
    },
    {
      name: 'Silero VAD',
      url: 'https://github.com/snakers4/silero-vad',
      license: 'MIT',
      description: 'Lightweight Voice Activity Detection',
    },
    {
      name: 'React',
      url: 'https://react.dev/',
      license: 'MIT',
      description: 'JavaScript library for building user interfaces',
    },
    {
      name: 'Tailwind CSS',
      url: 'https://tailwindcss.com/',
      license: 'MIT',
      description: 'Utility-first CSS framework',
    },
    {
      name: 'Zustand',
      url: 'https://github.com/pmndrs/zustand',
      license: 'MIT',
      description: 'Small, fast, scalable state management',
    },
    {
      name: 'NVIDIA Integrate API',
      url: 'https://integrate.api.nvidia.com/',
      license: 'NVIDIA Terms',
      description: 'Hosted LLM inference (stepfun-ai/step-3.7-flash)',
    },
  ];

  const version = '0.1.0';
  const buildDate = '2026-08-17';

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">About OminiVoice</h1>
        <p className="mt-2 text-gray-600">
          Version {version} · Built {buildDate}
        </p>
      </div>

      <div className="card">
        <div className="card-header">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center">
            <BookOpenIcon className="w-5 h-5 mr-2 text-primary-600" />
            What is OminiVoice?
          </h2>
        </div>
        <div className="card-body">
          <p className="text-gray-700 mb-4">
            OminiVoice is a multi-tenant SaaS platform for configuring and testing AI voice agents.
            Users can create inbound and outbound voice agents with detailed prompt configurations,
            get API keys and webhook URLs for integration, and test agents directly in their browser
            using simulated WebRTC calls — no phone numbers or telephony providers required.
          </p>
          <ul className="space-y-2 text-gray-700 list-disc list-inside">
            <li><strong>Voice Agent Configuration:</strong> 14 prompt fields per direction (inbound/outbound) for granular control</li>
            <li><strong>AI Prompt Rewriting:</strong> One-click prompt optimization using LLM</li>
            <li><strong>Simulated Test Calls:</strong> WebRTC-based in-browser testing with live transcript</li>
            <li><strong>Dual-Stack Architecture:</strong> Local (CPU) or NVIDIA NIM (GPU) voice engines</li>
            <li><strong>API & Webhook System:</strong> Per-agent keys and deterministic webhook URLs</li>
            <li><strong>Multi-Tenant:</strong> Isolated agents, keys, and logs per user</li>
          </ul>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center">
            <CodeBracketIcon className="w-5 h-5 mr-2 text-primary-600" />
            API Documentation
          </h2>
        </div>
        <div className="card-body">
          <p className="text-gray-700 mb-4">
            The API is documented using OpenAPI/Swagger. You can explore the interactive documentation at:
          </p>
          <div className="space-y-3">
            <a
              href="/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="btn-primary inline-flex items-center"
            >
              <CodeBracketIcon className="w-5 h-5 mr-2" />
              Swagger UI (/docs)
            </a>
            <a
              href="/redoc"
              target="_blank"
              rel="noopener noreferrer"
              className="btn-secondary inline-flex items-center"
            >
              <BookOpenIcon className="w-5 h-5 mr-2" />
              ReDoc (/redoc)
            </a>
          </div>
          <p className="text-sm text-gray-500 mt-4">
            These endpoints are available in development mode. In production, access may be restricted.
          </p>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center">
            <CubeIcon className="w-5 h-5 mr-2 text-primary-600" />
            Open Source Components
          </h2>
        </div>
        <div className="card-body">
          <p className="text-gray-700 mb-4">
            OminiVoice is built on the shoulders of giants. Here are the open-source components we use:
          </p>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Component</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">License</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Description</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {openSourceComponents.map((comp) => (
                  <tr key={comp.name} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <a href={comp.url} target="_blank" rel="noopener noreferrer" className="font-medium text-primary-600 hover:underline flex items-center">
                        {comp.name}
                        <LinkIcon className="w-4 h-4 ml-1 text-gray-400" />
                      </a>
                    </td>
                    <td className="px-4 py-3">
                      <span className="badge badge-gray">{comp.license}</span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">{comp.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center">
            <HeartIcon className="w-5 h-5 mr-2 text-primary-600" />
            Support & Contact
          </h2>
        </div>
        <div className="card-body">
          <div className="space-y-4">
            <div className="flex items-center space-x-3 p-4 bg-gray-50 rounded-lg">
              <LinkIcon className="w-6 h-6 text-primary-600" />
              <div>
                <p className="font-medium text-gray-900">GitHub Repository</p>
                <p className="text-sm text-gray-600">
                  <a href="https://github.com/S-V-J/ominivoice" target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:underline">
                    github.com/S-V-J/ominivoice
                  </a>
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-3 p-4 bg-gray-50 rounded-lg">
              <CodeBracketIcon className="w-6 h-6 text-primary-600" />
              <div>
                <p className="font-medium text-gray-900">Report Issues</p>
                <p className="text-sm text-gray-600">
                  <a href="https://github.com/S-V-J/ominivoice/issues" target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:underline">
                    GitHub Issues
                  </a>
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-3 p-4 bg-gray-50 rounded-lg">
              <BookOpenIcon className="w-6 h-6 text-primary-600" />
              <div>
                <p className="font-medium text-gray-900">Documentation</p>
                <p className="text-sm text-gray-600">
                  See <code className="bg-gray-100 px-1.5 py-0.5 rounded text-sm">/docs</code> folder in the repository
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-3 p-4 bg-gray-50 rounded-lg">
              <HeartIcon className="w-6 h-6 text-red-500" />
              <div>
                <p className="font-medium text-gray-900">Email</p>
                <p className="text-sm text-gray-600">stjl093@gmail.com</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center">
            <CodeBracketIcon className="w-5 h-5 mr-2 text-primary-600" />
            Changelog
          </h2>
        </div>
        <div className="card-body">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-4 border-primary-600 border-t-transparent"></div>
            </div>
          ) : (
            <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto text-sm max-h-96 overflow-y-auto">
              {changelog}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}