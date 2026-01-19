import { FaCoffee, FaHeart } from 'react-icons/fa';
import { GiRaceCar } from 'react-icons/gi';
import ActionButton from '../components/buttons/ActionButton';
import Card from '../components/common/Card';

function Support() {
  const supportOptions = [
    {
      id: 'coffee',
      title: 'Buy Me a Coffee',
      description: 'Support the project with a one-time donation. Every contribution helps keep CarModPicker running!',
      icon: <FaCoffee className="text-3xl" />,
      color: 'from-amber-500 to-orange-500',
      link: 'https://buymeacoffee.com/webbpulse', // Replace with actual link
      buttonText: 'Buy Me a Coffee',
    },
    
  ];

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative py-20 px-4 overflow-hidden">
        {/* Background Elements */}
        <div className="absolute inset-0">
          <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-gradient-to-r from-amber-500/20 to-orange-500/20 rounded-full blur-3xl animate-float"></div>
          <div
            className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-gradient-to-r from-purple-500/20 to-pink-500/20 rounded-full blur-3xl animate-float"
            style={{ animationDelay: '1s' }}
          ></div>
        </div>

        <div className="container mx-auto relative z-10">
          <div className="text-center max-w-5xl mx-auto">
            <div className="animate-fadeInScale">
              {/* Icon */}
              <div className="flex justify-center mb-8">
                <div className="relative">
                  <div className="w-24 h-24 bg-gradient-to-br from-amber-500 via-orange-500 to-red-500 rounded-3xl flex items-center justify-center shadow-2xl animate-glow">
                    <FaCoffee className="text-white text-4xl" />
                  </div>
                  <div className="absolute -inset-2 bg-gradient-to-br from-amber-500/30 via-orange-500/30 to-red-500/30 rounded-3xl blur-xl animate-pulse"></div>
                </div>
              </div>

              {/* Title */}
              <h1 className="text-6xl md:text-7xl font-bold mb-8">
                <span className="text-gradient">Support CarModPicker</span>
              </h1>

              {/* Subtitle */}
              <p className="text-xl md:text-2xl text-neutral-300 mb-8 leading-relaxed">
                Help us keep the platform running and improving
              </p>

              <p className="text-lg text-neutral-400 mb-12 max-w-4xl mx-auto leading-relaxed">
                CarModPicker is built with passion and dedication to serve the car enthusiast community. 
                Your support helps us maintain servers, develop new features, and keep the platform free 
                for everyone. Every contribution, no matter how small, makes a difference!
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Support Options Section */}
      <section className="py-24 px-4">
        <div className="container mx-auto">
          <div className="text-center mb-20 animate-slideInUp">
            <h2 className="text-5xl md:text-6xl font-bold mb-8">
              <span className="text-gradient">Ways to Support</span>
            </h2>
            <p className="text-xl text-neutral-400 max-w-3xl mx-auto leading-relaxed">
              Choose the method that works best for you
            </p>
          </div>

          <div className="flex justify-center">
            {supportOptions.map((option, index) => (
              <Card
                key={option.id}
                variant="glass"
                interactive
                className="group animate-slideInUp text-center max-w-md w-full"
                style={{ animationDelay: `${index * 0.1}s` }}
              >
                <div
                  className={`w-16 h-16 bg-gradient-to-br ${option.color} rounded-2xl flex items-center justify-center text-white mx-auto mb-6 group-hover:scale-110 transition-transform duration-300 shadow-lg`}
                >
                  {option.icon}
                </div>
                <h3 className="text-2xl font-semibold text-white mb-4 group-hover:text-gradient transition-colors">
                  {option.title}
                </h3>
                <p className="text-neutral-400 mb-6 leading-relaxed">
                  {option.description}
                </p>
                <a
                  href={option.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block"
                >
                  <ActionButton className="w-full bg-gradient-to-r from-primary-500 to-primary-600 hover:from-primary-600 hover:to-primary-700 text-white">
                    {option.buttonText}
                  </ActionButton>
                </a>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Why Support Section */}
      <section className="py-24 px-4">
        <div className="container mx-auto">
          <Card variant="glass" className="p-12 max-w-4xl mx-auto">
            <div className="text-center">
              <div className="flex justify-center mb-6">
                <FaHeart className="text-5xl text-red-500 animate-pulse" />
              </div>
              <h2 className="text-4xl md:text-5xl font-bold mb-8">
                <span className="text-gradient">Why Your Support Matters</span>
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mt-12 text-left">
                <div>
                  <h3 className="text-xl font-semibold text-white mb-3 flex items-center">
                    <GiRaceCar className="mr-3 text-primary-400" />
                    Keep It Free
                  </h3>
                  <p className="text-neutral-400 leading-relaxed">
                    Your donations help us keep CarModPicker free and accessible to all car enthusiasts, 
                    without requiring subscriptions or paywalls for core features.
                  </p>
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-white mb-3 flex items-center">
                    <GiRaceCar className="mr-3 text-primary-400" />
                    Better Features
                  </h3>
                  <p className="text-neutral-400 leading-relaxed">
                    Support enables us to develop new features, improve performance, and enhance the 
                    overall user experience for the entire community.
                  </p>
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-white mb-3 flex items-center">
                    <GiRaceCar className="mr-3 text-primary-400" />
                    Reliable Service
                  </h3>
                  <p className="text-neutral-400 leading-relaxed">
                    Contributions help maintain servers, ensure uptime, and provide reliable access 
                    to your build lists and parts catalog.
                  </p>
                </div>
                <div>
                  <h3 className="text-xl font-semibold text-white mb-3 flex items-center">
                    <GiRaceCar className="mr-3 text-primary-400" />
                    Community Growth
                  </h3>
                  <p className="text-neutral-400 leading-relaxed">
                    Your support helps us grow the community, add more cars and parts, and create 
                    a better platform for car enthusiasts worldwide.
                  </p>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </section>

      {/* Thank You Section */}
      <section className="py-24 px-4 pb-24">
        <div className="container mx-auto">
          <div className="text-center max-w-3xl mx-auto">
            <div className="animate-fadeInScale">
              <h2 className="text-4xl md:text-5xl font-bold mb-6">
                <span className="text-gradient">Thank You!</span>
              </h2>
              <p className="text-xl text-neutral-300 leading-relaxed">
                Whether you choose to support us financially or by being an active member of our 
                community, we appreciate you being part of CarModPicker. Together, we're building 
                something amazing for car enthusiasts everywhere.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

export default Support;
