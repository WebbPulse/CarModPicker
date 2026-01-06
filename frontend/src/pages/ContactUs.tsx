import Card from '../components/common/Card';

function ContactUs() {
  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative py-20 px-4 overflow-hidden">
        {/* Enhanced Background Elements */}
        <div className="absolute inset-0">
          <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-gradient-to-r from-blue-500/20 to-purple-500/20 rounded-full blur-3xl animate-float"></div>
          <div
            className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-gradient-to-r from-pink-500/20 to-red-500/20 rounded-full blur-3xl animate-float"
            style={{ animationDelay: '1s' }}
          ></div>
          <div
            className="absolute top-1/2 left-1/2 w-64 h-64 bg-gradient-to-r from-green-500/20 to-blue-500/20 rounded-full blur-3xl animate-float"
            style={{ animationDelay: '2s' }}
          ></div>
        </div>

        <div className="container mx-auto relative z-10">
          <div className="text-center max-w-5xl mx-auto">
            <div className="animate-fadeInScale">
              <h1 className="text-6xl md:text-7xl font-bold mb-8">
                <span className="text-gradient">Contact Us</span>
              </h1>
              <p className="text-xl md:text-2xl text-neutral-300 mb-8 leading-relaxed">
                We'd love to hear from you
              </p>
              <p className="text-lg text-neutral-400 mb-12 max-w-4xl mx-auto leading-relaxed">
                Have questions, feedback, or want to get in touch? We're here to
                help and always happy to connect with our community.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Business Inquiries Section */}
      <section className="py-24 px-4">
        <div className="container mx-auto text-center">
          <Card variant="glass" className="max-w-4xl mx-auto p-12">
            <div className="animate-fadeInScale">
              <h2 className="text-5xl md:text-6xl font-bold mb-8">
                <span className="text-gradient">Business Inquiries</span>
              </h2>
              <p className="text-xl text-neutral-400 mb-8 max-w-2xl mx-auto leading-relaxed">
                Interested in partnering with us or have a business proposal?
                We'd love to hear from you.
              </p>
              <p className="text-lg text-neutral-300 mb-4">
                Please send all business inquiries to:
              </p>
              <a
                href="mailto:tyler@webbpulse.com"
                className="text-2xl font-semibold text-gradient hover:underline inline-block"
              >
                tyler@webbpulse.com
              </a>
            </div>
          </Card>
        </div>
      </section>
    </div>
  );
}

export default ContactUs;
