# backer_upper.rb

#
# Joseph Yennaco, 30 September 2012
#

require 'fileutils'

class BackerUpper
  
  # Root directory for backing up data
  @@start_path = File.expand_path('~')
  
  # Items with the following names will be skipped and not backed up
  @@skip_items = ["iTunes", "iMovie Events", "iPhoto Library", "Applications", 
                  "Library", "Downloads", "Desktop", "Public", 
                  "iMovie Events.localized", "VirtualBox VMs", "VM_share", "Microsoft User Data"]
  
  # Files with the following extensions will not be updated if a newer version 
  # is found
  @@no_update_items = [".mp3", ".m4a", ".m4p", ".wma"]
  
  def self.backup_files
    Printer.output_major_status("Running Backer Upper...")
    volumes = Volumes.get_volumes
		
		if volumes.empty?
			Printer.output_minor_status("No Volumes to Backup To!", :complete)  
			return
		end
		
		selected_volumes = Volumes.get_selected_volumes("Type volumes to Backup To:")
		
		selected_volumes.each do |volume|
      if volume == "done"
        break
      else
        Printer.output_major_status("Backing up to " + volume + "...")
        backup_to_volume(volume)
        Printer.output_major_status("Backup to " + volume + " Complete!")
      end
	  end
    
    Printer.output_major_status("Done Backer Upper.")
  end
  
  private # Private methods follow
  
  def self.backup_to_volume(volume)
    # Build the absolute volume path
		volume_path = File.join('', 'Volumes', volume)
		
		if not Volumes.writable?(volume)
		  Printer.output_error("Backup Drive #{volume} is not writable! Skipping...")
		  return
	  end
	  
	  backup(@@start_path, volume_path)
  end
  
  def self.backup(source_path, target_path)
    
    source = File.basename(source_path)
    return if skip?(source)
    
    Printer.output_minor_status("Backing Up:\t\t#{source_path}", :none)
    
    # If the source_path is a file, back it up if needed
    if File.file?(source_path)
      
      # If the file already exists on the backup, check to see if there is a 
      # newer version
      
      if File.exist?(target_path)
        # Check modified time and the extension (certain extensions aren't updated)
        source_mtime = File.mtime(source_path)
        target_mtime = File.mtime(target_path)
        difference = source_mtime - target_mtime
        difference = 0 if difference == 3600.0
        extension = File.extname(source).downcase
        
        if (difference > 10) and not @@no_update_items.include?(extension)
          FileUtils.cp(source_path,target_path,:preserve=>true)
          Printer.output_minor_status("Updated Backup:\t#{target_path}", :none)
          Printer.output_minor_status("="*120, :none)
        else
          Printer.output_minor_status("Backup Exists:\t#{target_path}", :none)
          Printer.output_minor_status("="*120, :none)
        end
      
      else
        # Copy file to backup
        FileUtils.cp(source_path,target_path,:preserve=>true)
        Printer.output_minor_status("Created Backup:\t#{target_path}", :none)
        Printer.output_minor_status("="*120, :none)
      end
      
    # If the source_path is a directory, recursively traverse it
    elsif File.directory?(source_path)
      
      # Make the target directory if it doesn't exist
      Dir.mkdir(target_path) unless File.exist?(target_path)
      
      # Get the list of items in the directory and filter out unwanteds
      items = Dir.entries(source_path)
      items.delete_if { |x| skip?(x) }
      items.delete_if { |x| x.start_with?(".") }
      items.sort!
      
      # Traverse the items in this directory calling backup recursively
  	  items.each do |item|
  	    new_source_path = File.join(source_path, item)
  	    new_target_path = File.join(target_path, item)
        backup(new_source_path, new_target_path)
      end
    end
  end
  
  def self.skip?(item)
    return true if @@skip_items.include?(item)
    return false
  end
  
end
