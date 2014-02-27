class Logger

	def self.output_major_status(message="Processing")
		puts "-" * 60
		puts "#{message}".center(60)
		puts "-" * 60
	end

	def self.output_minor_status(message="Processing", type=nil)
		print "  #{message}"
		puts "." if type == :complete
		puts "" if type == :none
		puts "..." if type == nil
	end
	
	def self.output_error(message="Error")
		puts("\n  ERROR===> #{message} <===ERROR\n")
	end
	
	def self.output_user_info(message="Info")
		puts("\t#{message}")
	end
	
	def self.get_user_input(message="Input")
		print("\t#{message}: ")
	end
	
	def self.output_user_alert(message="Alert")
		puts("\t===> #{message} <===")
	end

end